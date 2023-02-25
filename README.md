# SD webui txt2img script

This script is meant for the stable diffusion webui by automatic1111 -> https://github.com/AUTOMATIC1111

Put the script `process_png_metadata.py` in the "stable-diffusion-webui\scripts folder then reload the webui and Simply drag 
and drop or upload image files to modify a prompt, override default settings to modify images again.

This file is specifically meant for a batch process of image files with metadata applicable to the txt2img section
of the webui. Allows user to easily use the hires fix upscale to get better images instead of img2img upscale.

overall features include:
  - upload multiple files to process
  - add/delete tags from a positive prompt
  - override default generation settings with image metadata

### script interface
![alt text](https://github.com/thundaga/StableDiffusionScripts/blob/main/screenshot.PNG?raw=true)

source references this discussion -> https://github.com/AUTOMATIC1111/stable-diffusion-webui/discussions/4938
made this script through feature request issue #7462 -> https://github.com/AUTOMATIC1111/stable-diffusion-webui/issues/7462



