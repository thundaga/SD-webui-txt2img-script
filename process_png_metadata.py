import gradio as gr
import re
from PIL import Image
import os
from collections import namedtuple

import modules.scripts as scripts
from modules import processing
from modules import images
from modules.processing import process_images, Processed
from modules.shared import state
import modules.shared as shared
from modules.shared import opts
from modules.generation_parameters_copypaste import parse_generation_parameters
from modules.extras import run_pnginfo

import json # DEBUG
# github repository -> https://github.com/thundaga/SD-webui-txt2img-script

class Script(scripts.Script): 

    # title of script on dropdown menu
    def title(self):

        return "Process PNG Metadata Info"

    # Script shows up only on txt2image section
    def show(self, is_img2img):

        return not is_img2img
    
    # set up ui to drag and drop the processed images and hold their file info
    def ui(self, is_img2img):

        tab_index = gr.State(value=0)

        with gr.Row().style(equal_height=False, variant='compact'):
            with gr.Column(variant='compact'):
                with gr.Tabs(elem_id="mode_extras"):
                    with gr.TabItem('Batch Process', elem_id="extras_batch_process_tab") as tab_batch:
                        upload_imgs = gr.File(label="Batch Process", file_count="multiple", interactive=True, type="file", elem_id=self.elem_id("files"))

                    with gr.TabItem('Batch from Directory', elem_id="extras_batch_directory_tab") as tab_batch_dir:
                        input_dir = gr.Textbox(label="Input directory", **shared.hide_dirs, placeholder="Add input folder path", elem_id="files_batch_input_dir")
                        output_dir = gr.Textbox(label="Output directory", **shared.hide_dirs, placeholder="Add output folder path or Leave blank to use default path.", elem_id="files_batch_output_dir")
                
                # CheckboxGroup with all parameters assignable from the input image (output is a list with the Name of the Checkbox checked ex: ["Checkpoint", "Prompt"]) 
                options = gr.CheckboxGroup(["Checkpoint", "Prompt", "Negative Prompt", "Seed", "Variation Seed", "Variation Seed Strenght", "Sampler", "Steps", "CFG scale", "Width and Height", "Upscaler", "Denoising Strength", "Hires Scale or Width and Height", "Clip Skip", "Face restoration"], label="Assign from input image", info="Checked : Assigned from the input images\nUnchecked : Assigned from the UI")

                gr.HTML("<p style=\"margin-bottom:0.75em\">Optional tags to remove or add in front/end of a positive prompt on all images</p>")
                front_tags = gr.Textbox(label="Tags to add at the front")
                back_tags = gr.Textbox(label="Tags to add at the end")
                remove_tags = gr.Textbox(label="Tags to remove")

        tab_batch.select(fn=lambda: 0, inputs=[], outputs=[tab_index])
        tab_batch_dir.select(fn=lambda: 1, inputs=[], outputs=[tab_index])

        return [tab_index,upload_imgs,front_tags,back_tags,remove_tags,input_dir,output_dir,options]

    # Files are open as images and the png info is set to the processed class for each iterated process
    def run(self,p,tab_index,upload_imgs,front_tags,back_tags,remove_tags,input_dir,output_dir,options):

        image_batch = []

        # Operation based on current batch process tab
        if tab_index == 0:
            for img in upload_imgs:
                if run_pnginfo(Image.open(img.name))[1] != None:
                    image_batch.append(Image.open(img.name))
        elif tab_index == 1:
            assert not shared.cmd_opts.hide_ui_dir_config, '--hide-ui-dir-config option must be disabled'
            assert input_dir, 'input directory not selected'

            images_dir = shared.listfiles(input_dir)
            for img in images_dir:
                if run_pnginfo(Image.open(img))[1] != None:
                    image_batch.append(Image.open(img))

        if tab_index == 1 and output_dir != '':
            p.do_not_save_samples = True
    
        image_count = len(image_batch)
        state.job_count = image_count

        images_list = []
        all_prompts = []
        infotexts = []

        for image in image_batch:
            state.job = f"{state.job_no + 1} out of {state.job_count}"

            my_text = run_pnginfo(image)[1]
            parsed_text = parse_generation_parameters(my_text)

            if "Prompt" in options and 'Prompt' in parsed_text:
                p.prompt = parsed_text['Prompt']

                if remove_tags:
                    remove_tags = remove_tags.strip("\n")
                    tags = [x.strip() for x in remove_tags.split(',')]
                    while("" in tags):
                        tags.remove("")
                    text = p.prompt

                    for tag in tags:
                        text = re.sub("\(\(" + tag + "\)\)|\(" + tag + ":.*?\)|<" + tag + ":.*?>|<" + tag + ">", "", text)
                        text = re.sub(r'\([^\(]*(%s)\S*\)' % tag, '', text)
                        text = re.sub(r'\[[^\[]*(%s)\S*\]' % tag, '', text)
                        text = re.sub(r'<[^<]*(%s)\S*>' % tag, '', text)
                        text = re.sub(r'\b' + tag + r'\b', '', text)

                    # remove consecutive comma patterns with a coma and space
                    pattern = re.compile(r'(,\s){2,}')
                    text = re.sub(pattern, ', ', text)

                    # remove final comma at start of prompt
                    text = text.replace(", ", "", 1)
                    p.prompt = text

                if front_tags:
                    if front_tags.endswith(' ') == False and front_tags.endswith(',') == False:
                        front_tags = front_tags + ','
                    p.prompt = ''.join([front_tags, p.prompt])

                if back_tags:
                    if back_tags.startswith(' ') == False and back_tags.startswith(',') == False:
                        back_tags = ',' + back_tags
                    p.prompt = ''.join([p.prompt, back_tags])

            if "Checkpoint" in options and 'Model hash' in parsed_text:
                p.override_settings['sd_model_checkpoint'] = parsed_text['Model hash']
            if "Negative Prompt" in options and 'Negative prompt' in parsed_text:
                p.negative_prompt = parsed_text['Negative prompt']
            if "Seed" in options and 'Seed' in parsed_text:
                p.seed = float(parsed_text['Seed'])
            if "Variation Seed" in options and 'Variation seed' in parsed_text:
                p.subseed = float(parsed_text['Variation seed'])
            if "Variation Seed Strenght" in options and 'Variation seed strength' in parsed_text:
                p.subseed_strength = float(parsed_text['Variation seed strength'])
            if "Sampler" in options and 'Sampler' in parsed_text:
                p.sampler_name = parsed_text['Sampler']
            if "Steps" in options and 'Steps' in parsed_text:
                p.steps = int(parsed_text['Steps'])
            if "CFG scale" in options and 'CFG scale' in parsed_text:
                p.cfg_scale = float(parsed_text['CFG scale'])
            if "Width and Height" in options and 'Size-1' in parsed_text:
                p.width = int(parsed_text['Size-1'])
            if "Width and Height" in options and 'Size-2' in parsed_text:
                p.height = int(parsed_text['Size-2'])
            if "Upscaler" in options and 'Hires upscaler' in parsed_text:
                p.hr_upscaler = parsed_text['Hires upscaler']
            if "Denoising Strength" in options and 'Denoising strength' in parsed_text:
                p.denoising_strength = float(parsed_text['Denoising strength'])
            if "Hires Scale or Width and Height" in options:
                # Reset hr_settings to avoid wrong settings
                p.hr_scale = None
                p.hr_resize_x = int(0)
                p.hr_resize_y= int(0)
                if 'Hires upscale' in parsed_text:
                    p.hr_scale = float(parsed_text['Hires upscale'])
                if 'Hires resize-1' in parsed_text:
                    p.hr_resize_x = int(parsed_text['Hires resize-1'])
                if 'Hires resize-2' in parsed_text:
                    p.hr_resize_y = int(parsed_text['Hires resize-2'])
            if "Clip Skip" in options and 'Clip skip' in parsed_text:
                p.override_settings['CLIP_stop_at_last_layers'] = int(parsed_text['Clip skip'])
            if "Face restoration" in options and 'Face restoration' in parsed_text:
                p.restore_faces = parsed_text['Face restoration']
            
            proc = process_images(p)

            # Reset Hires prompts (else the prompts of the first image will be used as Hires prompt for all the others)
            p.hr_prompt = ""
            p.hr_negative_prompt = ""

            # Reset extra_generation_params as it stores the Hires resize and scale (Avoid having wrong info in the infotext)
            p.extra_generation_params = {}

            # Modified directory to save generated images in cache
            if tab_index == 1 and output_dir != '':
                for n, processed_image in enumerate(proc.images):
                    images.save_image(image=processed_image, path=output_dir, basename='', existing_info=processed_image.info)

            images_list += proc.images
            all_prompts += proc.all_prompts
            infotexts += proc.infotexts

            
        processing.fix_seed(p)

        return Processed(p, images_list, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)
