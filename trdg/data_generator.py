import os
import random as rnd

from PIL import Image, ImageFilter, ImageStat

from nb_utils.error_handling import trace_error

from trdg import computer_text_generator, background_generator, distorsion_generator
from trdg.utils import mask_to_bboxes

try:
    from trdg import handwritten_text_generator
except ImportError as e:
    print("Missing modules for handwritten text generation.")

import json
import re


class FakeTextDataGenerator(object):
    @classmethod
    def generate_from_tuple(cls, t):
        """
            Same as generate, but takes all parameters as one tuple
        """

        cls.generate(*t)

    @classmethod
    def generate(
        cls,
        index,
        text,
        font,
        out_dir,
        size,
        extension,
        skewing_angle,
        random_skew,
        blur,
        random_blur,
        background_type,
        distorsion_type,
        distorsion_orientation,
        is_handwritten,
        name_format,
        width,
        alignment,
        text_color,
        orientation,
        space_width,
        character_spacing,
        margins,
        fit,
        output_mask,
        word_split,
        image_dir,
        stroke_width=0, 
        stroke_fill="#282828",
        image_mode="RGB", 
        output_bboxes=0,
        random_margin=False,
    ):
        try:
            image = None

            # 15 dec 2022 : if output bboxes enabled multiple spaces in words cause issue, added below to fix
            if output_bboxes:
                # replace-multiple-whitespaces-by-one in input string
                text = re.sub('\s+',' ', text)

            margin_top, margin_left, margin_bottom, margin_right = margins

            # update 12 April 2023 -- add random margin if enabled
            if random_margin:
                from random import randint
                margin_top = randint(0, margin_top + 1)
                margin_left = randint(0, margin_left + 1)
                margin_bottom = randint(0, margin_bottom + 1)
                margin_right = randint(0, margin_right + 1)
            # end update
                
            horizontal_margin = margin_left + margin_right
            vertical_margin = margin_top + margin_bottom

            # print(f"Data generator text: ", text)

            ##########################
            # Create picture of text #
            ##########################
            if is_handwritten:
                if orientation == 1:
                    raise ValueError("Vertical handwritten text is unavailable")
                image, mask = handwritten_text_generator.generate(text, text_color)
            else:
                image, mask = computer_text_generator.generate(
                    text,
                    font,
                    text_color,
                    size,
                    orientation,
                    space_width,
                    character_spacing,
                    fit,
                    word_split,
                    stroke_width, 
                    stroke_fill,
                )
            random_angle = rnd.randint(0 - skewing_angle, skewing_angle)

            rotated_img = image.rotate(
                skewing_angle if not random_skew else random_angle, expand=1
            )

            rotated_mask = mask.rotate(
                skewing_angle if not random_skew else random_angle, expand=1
            )

            #############################
            # Apply distorsion to image #
            #############################
            if distorsion_type == 0:
                distorted_img = rotated_img  # Mind = blown
                distorted_mask = rotated_mask
            elif distorsion_type == 1:
                distorted_img, distorted_mask = distorsion_generator.sin(
                    rotated_img,
                    rotated_mask,
                    vertical=(distorsion_orientation == 0 or distorsion_orientation == 2),
                    horizontal=(distorsion_orientation == 1 or distorsion_orientation == 2),
                )
            elif distorsion_type == 2:
                distorted_img, distorted_mask = distorsion_generator.cos(
                    rotated_img,
                    rotated_mask,
                    vertical=(distorsion_orientation == 0 or distorsion_orientation == 2),
                    horizontal=(distorsion_orientation == 1 or distorsion_orientation == 2),
                )
            else:
                distorted_img, distorted_mask = distorsion_generator.random(
                    rotated_img,
                    rotated_mask,
                    vertical=(distorsion_orientation == 0 or distorsion_orientation == 2),
                    horizontal=(distorsion_orientation == 1 or distorsion_orientation == 2),
                )

            ##################################
            # Resize image to desired format #
            ##################################

            # Horizontal text
            if orientation == 0:
                new_width = int(
                    distorted_img.size[0]
                    * (float(size - vertical_margin) / float(distorted_img.size[1]))
                )
                try:
                    resized_img = distorted_img.resize(
                        (new_width, size - vertical_margin), Image.ANTIALIAS
                    )
                except Exception as e:
                    # distorted_img.save("error.png")
                    # import pdb;pdb.set_trace()
                    return

                resized_mask = distorted_mask.resize((new_width, size - vertical_margin), Image.NEAREST)
                background_width = width if width > 0 else new_width + horizontal_margin
                background_height = size
            # Vertical text
            elif orientation == 1:
                new_height = int(
                    float(distorted_img.size[1])
                    * (float(size - horizontal_margin) / float(distorted_img.size[0]))
                )
                resized_img = distorted_img.resize(
                    (size - horizontal_margin, new_height), Image.ANTIALIAS
                )
                resized_mask = distorted_mask.resize(
                    (size - horizontal_margin, new_height), Image.NEAREST
                )
                background_width = size
                background_height = new_height + vertical_margin
            else:
                raise ValueError("Invalid orientation")

            # resized_img.save(os.path.join(out_dir, "resized_img.png"))

            #############################
            # Generate background image #
            #############################
            if background_type == 0:
                background_img = background_generator.gaussian_noise(
                    background_height, background_width
                )
            elif background_type == 1:
                background_img = background_generator.plain_white(
                    background_height, background_width
                )
            elif background_type == 2:
                background_img = background_generator.quasicrystal(
                    background_height, background_width
                )
            elif background_type == 4:
                ## Transparent background
                # background_img = Image.new('RGBA', (background_width, background_height), (0, 0, 0, 0))
                ## For pure black text use diffrent background color -- to avoid issue in bounding boxes mask 
                background_img = Image.new('RGBA', (background_width, background_height), (255, 255, 255, 0))
                
                # background_img.save(os.path.join(out_dir, "tranparent-bg.png"))
            else:
                #############################################
                ## Modified on -- 12 march 2022 
                ## to get cropped backfround info and cordinates
                ## for joining patch file 
                #############################################
                background_img, cordinates, bg_image_file = background_generator.image(
                    background_height, background_width, image_dir
                )
                # print(f"Index: ", index)
                # print(f"bg_image_file :", bg_image_file)
                # print(f"cordinates: ", cordinates)

                if output_bboxes:
                    ## TODO -- Add separate flag to control saving of bg and cropped area meta
                    dictionary = {
                        "index": index,
                        "bg_image_file": bg_image_file,
                        "cropped_area_cordinates": cordinates,
                    }
                    # Serializing json 
                    json_object = json.dumps(dictionary, indent = 4)
                    
                    # Writing to sample.json
                    with open(os.path.join(out_dir, f"{index}_bgcrop.json"), "w") as outfile:
                        outfile.write(json_object)
                        
            background_mask = Image.new(
                "RGB", (background_width, background_height), (0, 0, 0)
            )

            ##############################################################
            # Comparing average pixel value of text and background image #
            ##############################################################
            try:
                resized_img_st = ImageStat.Stat(resized_img, resized_mask.split()[2])
                background_img_st = ImageStat.Stat(background_img) 

                resized_img_px_mean = sum(resized_img_st.mean[:2]) / 3
                background_img_px_mean = sum(background_img_st.mean) / 3

                if abs(resized_img_px_mean - background_img_px_mean) < 15:
                    print("value of mean pixel is too similar. Ignore this image")

                    print("resized_img_st \n {}".format(resized_img_st.mean))
                    print("background_img_st \n {}".format(background_img_st.mean))

                    return
            except Exception as err:
                return

            #############################
            # Place text with alignment #
            #############################

            new_text_width, _ = resized_img.size

            if alignment == 0 or width == -1:
                background_img.paste(resized_img, (margin_left, margin_top), resized_img)
                background_mask.paste(resized_mask, (margin_left, margin_top))
            elif alignment == 1:
                background_img.paste(
                    resized_img,
                    (int(background_width / 2 - new_text_width / 2), margin_top),
                    resized_img,
                )
                background_mask.paste(
                    resized_mask,
                    (int(background_width / 2 - new_text_width / 2), margin_top),
                )
            else:
                background_img.paste(
                    resized_img,
                    (background_width - new_text_width - margin_right, margin_top),
                    resized_img,
                )
                background_mask.paste(
                    resized_mask,
                    (background_width - new_text_width - margin_right, margin_top),
                )

            ############################################
            # Change background image mode (RGB, grayscale, etc.) #
            ############################################
            background_img = background_img.convert(image_mode)
            background_mask = background_mask.convert(image_mode) 
            
            #######################
            # Apply gaussian blur #
            #######################

            gaussian_filter = ImageFilter.GaussianBlur(
                radius=blur if not random_blur else rnd.randint(0, blur)
            )
            final_image = background_img.filter(gaussian_filter)
            final_mask = background_mask.filter(gaussian_filter)
            
            ## For keeping transparency -RGBA -- it not showing output bboxes
            # ############################################
            # # Change image mode (RGB, grayscale, etc.) #
            # ############################################
            
            if image_mode == "RGBA":
                ## if RGBA and transparent background mode 4 it making text unclear and not visible sometime
                ## if we convert so -- skipping
                pass
            else:
                # RGB, grayscale, etc.
                final_image = final_image.convert(image_mode)
                final_mask = final_mask.convert(image_mode) 

            #####################################
            # Generate name for resulting image #
            #####################################
            # We remove spaces if space_width == 0
            if space_width == 0:
                text = text.replace(" ", "")
            if name_format == 0:
                name = "{}_{}".format(text, str(index))
            elif name_format == 1:
                name = "{}_{}".format(str(index), text)
            elif name_format in [2, 3, 4]:
                name = str(index)
            else:
                print("{} is not a valid name format. Using default.".format(name_format))
                name = "{}_{}".format(text, str(index))

            image_name = "{}.{}".format(name, extension)
            mask_name = "{}_mask.png".format(name)
            box_name = "{}_boxes.txt".format(name)
            tess_box_name = "{}.box".format(name)


            # Save the image
            if out_dir is not None:
                final_image.save(os.path.join(out_dir, image_name))
                
                if name_format == 3:
                    # save label
                    txt_filename = os.path.join(out_dir, f"{str(index)}.txt")
                    with open(txt_filename, 'w', encoding='utf-8') as f:
                        f.write(text)
                
                if name_format == 4:
                    # no labels saved for format 4
                    pass

                ## If image RGBA -- then convert to RGB to properly get word bounding boxes
                if image_mode == "RGBA":
                    final_image = final_image.convert("RGB")
                    final_mask = final_mask.convert("RGB")

                if output_mask == 1:
                    final_mask.save(os.path.join(out_dir, mask_name))

                if output_bboxes == 1:
                    bboxes = mask_to_bboxes(final_mask)
                    with open(os.path.join(out_dir, box_name), "w") as f:
                        for bbox in bboxes:
                            f.write(" ".join([str(v) for v in bbox]) + "\n")
                if output_bboxes == 2 or output_bboxes == 3:
                    bboxes = mask_to_bboxes(final_mask, tess=True)
                    with open(os.path.join(out_dir, tess_box_name), "w") as f:
                        for bbox, char in zip(bboxes, text):
                            f.write(" ".join([char] + [str(v) for v in bbox] + ['0']) + "\n")

            else:
                if output_mask == 1:
                    return final_image, final_mask
                return final_image

        except Exception as e:
            print(f"Exception in ... Index: ", index, " text: ", text, " Exception:", e)
            full_error = trace_error()
            print(full_error)
            return
