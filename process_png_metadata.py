import gradio as gr
import re
from PIL import Image
import pathlib

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

def int_convert(text: str) -> int:
    return int(text)

def float_convert(text: str) -> float:
    return float(text)

def boolean_convert(text: str) -> bool:
    return True if (text == "true") else False

def hires_resize(p, parsed_text: dict):
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
    return p

def override_settings(p, options: list, parsed_text: dict):
    if "Checkpoint" in options and 'Model hash' in parsed_text:
        p.override_settings['sd_model_checkpoint'] = parsed_text['Model hash']
    if "Clip Skip" in options and 'Clip skip' in parsed_text:
        p.override_settings['CLIP_stop_at_last_layers'] = int(parsed_text['Clip skip'])
    return p

def width_height(p, parsed_text: dict):
    if 'Size-1' in parsed_text:
        p.width = int(parsed_text['Size-1'])
    if 'Size-2' in parsed_text:
        p.height = int(parsed_text['Size-2'])
    return p

def prompt_modifications(parsed_text: dict, front_tags: str, back_tags: str, remove_tags: str) -> str:
    prompt = parsed_text['Prompt']

    if remove_tags:
        remove_tags = remove_tags.strip("\n")
        tags = [x.strip() for x in remove_tags.split(',')]
        while("" in tags):
            tags.remove("")
        text = prompt

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
        prompt = text

    if front_tags:
        if front_tags.endswith(' ') == False and front_tags.endswith(',') == False:
            front_tags = front_tags + ','
        prompt = ''.join([front_tags, prompt])

    if back_tags:
        if back_tags.startswith(' ') == False and back_tags.startswith(',') == False:
            back_tags = ',' + back_tags
        prompt = ''.join([prompt, back_tags])
    return prompt

# build valid txt and image files e.g (txt(utf-8),img(png)) into valid parsed dictionaries with metadata info 
def build_file_list(file, tab_index: int, file_list: list[dict]) -> list[dict]:

    file = file.name if tab_index == 0 else file
    file_ext = pathlib.Path(file).suffix

    if file_ext == ".txt":
        text = open(file, "r", encoding="utf-8").read()
        if text != None and text != "":
            parsed_text = parse_generation_parameters(text)
            file_list.append(parsed_text)
    elif run_pnginfo(Image.open(file))[1] != None:
        text = run_pnginfo(Image.open(file))[1]
        parsed_text = parse_generation_parameters(text)
        file_list.append(parsed_text)

    return file_list

# key->(option name) : Values->tuple(metadata name, object property, property specific functions)
prompt_options = {
    "Checkpoint":                       ("Model hash", None, override_settings),
    "Prompt":                           ("Prompt", "prompt", prompt_modifications),
    "Negative Prompt":                  ("Negative prompt", "negative_prompt", None),
    "Seed":                             ("Seed", "seed", float_convert),
    "Variation Seed":                   ("Variation seed", "subseed", float_convert),
    "Variation Seed Strength":          ("Variation seed strength", "subseed_strength", float_convert),
    "Sampler":                          ("Sampler", "sampler_name", None),
    "Steps":                            ("Steps", "steps", int_convert),
    "CFG scale":                        ("CFG scale", "cfg_scale", float_convert),
    "Width and Height":                 (None, None, width_height),
    "Upscaler":                         ("Hires upscaler", "hr_upscaler", None),
    "Denoising Strength":               ("Denoising strength", "denoising_strength", float_convert),
    "Hires Scale or Width and Height":  (None, None, hires_resize),
    "Clip Skip":                        ("Clip skip", None, override_settings),
    "Face restoration":                 ("Face restoration", "restore_faces", boolean_convert),
}

class Script(scripts.Script): 

    def title(self):

        return "Process PNG Metadata Info"

    def show(self, is_img2img):

        return not is_img2img
    
    # set up ui to drag and drop the processed images and hold their file info
    def ui(self, is_img2img):

        tab_index = gr.State(value=0)

        with gr.Row().style(equal_height=False, variant='compact'):
            with gr.Column(variant='compact'):
                with gr.Tabs(elem_id="mode_extras"):
                    with gr.TabItem('Batch Process', elem_id="extras_batch_process_tab") as tab_batch:
                        upload_files = gr.File(label="Batch Process", file_count="multiple", interactive=True, type="file", elem_id=self.elem_id("files"))

                    with gr.TabItem('Batch from Directory', elem_id="extras_batch_directory_tab") as tab_batch_dir:
                        input_dir = gr.Textbox(label="Input directory", **shared.hide_dirs, placeholder="Add input folder path", elem_id="files_batch_input_dir")
                        output_dir = gr.Textbox(label="Output directory", **shared.hide_dirs, placeholder="Add output folder path or Leave blank to use default path.", elem_id="files_batch_output_dir")
                
                # CheckboxGroup with all parameters assignable from the input image (output is a list with the Name of the Checkbox checked ex: ["Checkpoint", "Prompt"]) 
                options = gr.Dropdown(list(prompt_options.keys()), label="Assign from input image", info="Select are assigned from the input, the rest from UI", multiselect = True)

                gr.HTML("<p style=\"margin-bottom:0.75em\">Optional tags to remove or add in front/end of a positive prompt on all images</p>")
                front_tags = gr.Textbox(label="Tags to add at the front")
                back_tags = gr.Textbox(label="Tags to add at the end")
                remove_tags = gr.Textbox(label="Tags to remove")

        tab_batch.select(fn=lambda: 0, inputs=[], outputs=[tab_index])
        tab_batch_dir.select(fn=lambda: 1, inputs=[], outputs=[tab_index])

        return [tab_index,upload_files,front_tags,back_tags,remove_tags,input_dir,output_dir,options]

    # Files are open as images and the png info is set to the processed class for each iterated process
    def run(self,p,tab_index,upload_files,front_tags,back_tags,remove_tags,input_dir,output_dir,options):

        image_batch = []

        # Operation based on current batch process tab
        if tab_index == 0:
            for file in upload_files:
                image_batch = build_file_list(file, tab_index, image_batch)
        elif tab_index == 1:
            assert not shared.cmd_opts.hide_ui_dir_config, '--hide-ui-dir-config option must be disabled'
            assert input_dir, 'input directory not selected'

            files_dir = shared.listfiles(input_dir)
            for file in files_dir:
                image_batch = build_file_list(file, tab_index, image_batch)

        if tab_index == 1 and output_dir != '':
            p.do_not_save_samples = True
    
        image_count = len(image_batch)
        state.job_count = image_count

        images_list = []
        all_prompts = []
        infotexts = []

        for parsed_text in image_batch:
            state.job = f"{state.job_no + 1} out of {state.job_count}"

            metadata, p_property, func = 0, 1, 2
            # go through dictionary and commit uniform actions on similar object properties
            for option, tuple in prompt_options.items():
                match option:
                    case "Prompt":
                        if option in options and  tuple[metadata] in parsed_text:
                            setattr(p, tuple[p_property], tuple[func](parsed_text,front_tags,back_tags,remove_tags))
                    case "Width and Height":
                        if option in options:
                            p = tuple[func](p, parsed_text)
                    case "Hires Scale or Width and Height":
                        if option in options:
                            p = tuple[func](p, parsed_text)
                    case "Checkpoint" | "Clip Skip":
                        p = tuple[func](p, options, parsed_text)
                    case _:
                        if option in options and tuple[metadata] in parsed_text:
                            if tuple[func] == None:
                                setattr(p, tuple[p_property], parsed_text[tuple[metadata]])
                            else:
                                setattr(p, tuple[p_property], tuple[func](parsed_text[tuple[metadata]]))

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
