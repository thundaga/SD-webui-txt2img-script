import modules.scripts as scripts
import gradio as gr
import re
from PIL import Image

from modules import processing
from modules.processing import process_images, Processed
from modules.shared import state
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

        with gr.Row().style(equal_height=False, variant='compact'):
            with gr.Column(variant='compact'):
                with gr.Tabs(elem_id="mode_extras"):
                    with gr.TabItem('Batch Process', elem_id="extras_batch_process_tab"):
                        files = gr.File(label="Batch Process", file_count="multiple", interactive=True, type="file", elem_id=self.elem_id("files"))

            
                prompt = gr.Checkbox(False, label="Assign Prompt")
                negative_prompt= gr.Checkbox(False, label="Assign Negative Prompt")
                seed = gr.Checkbox(False, label="Assign Seed")
                sampler_name = gr.Checkbox(False, label="Assign Sampler Name")
                steps = gr.Checkbox(False, label="Assign Steps")
                cfg_scale = gr.Checkbox(False, label="Assign CFG scale")
                width_height = gr.Checkbox(False, label="Assign Width and Height")
                denoising_strength = gr.Checkbox(False, label="Assign Denoising strength")

                gr.HTML("<p style=\"margin-bottom:0.75em\">Optional tags to remove or add in front/end of a positive prompt on all images</p>")
                front_tags = gr.Textbox(label="Tags to add at the front")
                back_tags = gr.Textbox(label="Tags to add at the end")
                remove_tags = gr.Textbox(label="Tags to remove")

        return [files, prompt,negative_prompt,seed,sampler_name,steps,cfg_scale,width_height,denoising_strength,front_tags,back_tags,remove_tags]

    # Files are open as images and the png info is set to the processed class for each iterated process
    def run(self,p,files,prompt,negative_prompt,seed,sampler_name,steps,cfg_scale,width_height,denoising_strength,front_tags,back_tags,remove_tags):

        image_batch = []
        for filepath in files:
            image_batch.append(Image.open(filepath.name))
       
        image_count = len(image_batch)
        state.job_count = image_count

        images = []
        all_prompts = []
        infotexts = []

        for image in image_batch:
            state.job = f"{state.job_no + 1} out of {state.job_count}"

            my_text = run_pnginfo(image)[1]
            parsed_text = parse_generation_parameters(my_text)

            if prompt and 'Prompt' in parsed_text:
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

            if negative_prompt and 'Negative prompt' in parsed_text:
                p.negative_prompt = parsed_text['Negative prompt']
            if seed and 'Seed' in parsed_text:
                p.seed = float(parsed_text['Seed'])
            if sampler_name and 'Sampler' in parsed_text:
                p.sampler_name = parsed_text['Sampler']
            if steps and 'Steps' in parsed_text:
                p.steps = int(parsed_text['Steps'])
            if cfg_scale and 'Seed' in parsed_text:
                p.cfg_scale = int(parsed_text['CFG scale'])                        
            if width_height and 'Size-1' in parsed_text:
                p.width = int(parsed_text['Size-1'])
            if width_height and 'Size-2' in parsed_text:
                p.height = int(parsed_text['Size-2'])
            if denoising_strength and 'Denoising strength' in parsed_text:
                p.denoising_strength = float(parsed_text['Denoising strength'])
        
            proc = process_images(p)

            images += proc.images
            all_prompts += proc.all_prompts
            infotexts += proc.infotexts

        processing.fix_seed(p)

        return Processed(p, images, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)


