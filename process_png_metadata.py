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

# github repository -> https://github.com/thundaga/SD-webui-txt2img-script

class Script(scripts.Script): 

    # title of script on dropdown menu
    def title(self):

        return "Process PNG Metadata Info"

    # Script shows up only on txt2image section
    # could not get it to only show for is_txt2img property so used "not is_img2img"
    # the script class apparently seems to set it to "script.is_txt2img = not is_img2img" too
    def show(self, is_img2img):

        return not is_img2img
    
    # set up ui to drag and drop the processed images and hold their file info
    # checkbox to boolean check which parameters to keep or not 
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
                
                prompt = gr.Checkbox(False, label="Assign Prompt")
                negative_prompt = gr.Checkbox(False, label="Assign Negative Prompt")
                seed = gr.Checkbox(False, label="Assign Seed")
                sampler_name = gr.Checkbox(False, label="Assign Sampler Name")
                steps = gr.Checkbox(False, label="Assign Steps")
                cfg_scale = gr.Checkbox(False, label="Assign CFG scale")
                width_height = gr.Checkbox(False, label="Assign Width and Height")
                denoising_strength = gr.Checkbox(False, label="Assign Denoising strength")

                options = (prompt,negative_prompt,seed,sampler_name,steps,cfg_scale,width_height,denoising_strength)

                gr.HTML("<p style=\"margin-bottom:0.75em\">Optional tags to remove or add in front/end of a positive prompt on all images</p>")
                front_tags = gr.Textbox(label="Tags to add at the front")
                back_tags = gr.Textbox(label="Tags to add at the end")
                remove_tags = gr.Textbox(label="Tags to remove")

        tab_batch.select(fn=lambda: 0, inputs=[], outputs=[tab_index])
        tab_batch_dir.select(fn=lambda: 1, inputs=[], outputs=[tab_index])

        return [tab_index,upload_imgs,front_tags,back_tags,remove_tags,input_dir,output_dir,*options]

    # Files are open as images and the png info is set to the processed class for each iterated process
    def run(self,p,tab_index,upload_imgs,front_tags,back_tags,remove_tags,input_dir,output_dir,*options):

        options_tuple = namedtuple('options_tuple', ['prompt','negative_prompt','seed','sampler_name','steps','cfg_scale','width_height', 'denoising_strength'])
        options = options_tuple(*options)

        image_batch = []

        # operation based on current batch process tab
        if tab_index == 0:
            for img in upload_imgs:
                image_batch.append(Image.open(img.name))
        elif tab_index == 1:
            assert not shared.cmd_opts.hide_ui_dir_config, '--hide-ui-dir-config option must be disabled'
            assert input_dir, 'input directory not selected'

            images_dir = shared.listfiles(input_dir)
            for img in images_dir:
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

            if options.prompt and 'Prompt' in parsed_text:
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

            if options.negative_prompt and 'Negative prompt' in parsed_text:
                p.negative_prompt = parsed_text['Negative prompt']
            if options.seed and 'Seed' in parsed_text:
                p.seed = float(parsed_text['Seed'])
            if options.sampler_name and 'Sampler' in parsed_text:
                p.sampler_name = parsed_text['Sampler']
            if options.steps and 'Steps' in parsed_text:
                p.steps = int(parsed_text['Steps'])
            if options.cfg_scale and 'CFG scale' in parsed_text:
                p.cfg_scale = float(parsed_text['CFG scale'])                        
            if options.width_height and 'Size-1' in parsed_text:
                p.width = int(parsed_text['Size-1'])
            if options.width_height and 'Size-2' in parsed_text:
                p.height = int(parsed_text['Size-2'])
            if options.denoising_strength and 'Denoising strength' in parsed_text:
                p.denoising_strength = float(parsed_text['Denoising strength'])
        
            proc = process_images(p)

            for n, processed_image in enumerate(proc.images):

                images.save_image(image=processed_image, path=output_dir, basename='', existing_info=processed_image.info)

            images_list += proc.images
            all_prompts += proc.all_prompts
            infotexts += proc.infotexts

            
        processing.fix_seed(p)

        return Processed(p, images_list, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)


