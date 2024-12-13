import contextlib

import gradio as gr
from modules import scripts

from scripts.Gel import Gelbooru

async def get_random_tags(include, exclude):
    include = include.replace(" ", "")
    exclude = exclude.replace(" ", "")
    if(include == "" and exclude == ""):
        gel_post = await Gelbooru().random_post()
    else:
        gel_post = await Gelbooru().random_post(tags=include.split(','), exclude_tags=exclude.split(','))
    return ', '.join(gel_post.get_tags()), gel_post

class ExampleScript(scripts.Script):
    
    def __init__(self) -> None:
        super().__init__()

    def title(self):
        return "Gelbooru Prompt Randomizer"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Accordion('Gelbooru Prompt Randomizer', open=False):
            with gr.Column():
                send_text_button = gr.Button(value='Randomize', variant='primary', size='lg')
                include_tags_textbox = gr.Textbox(label='Include Tags')
                exclude_tags_textbox = gr.Textbox(label='Exclude Tags')
                url_textbox = gr.Textbox(label='Url', show_copy_button=True, interactive=False)
        
        with contextlib.suppress(AttributeError):  # Ignore the error if the attribute is not present
            if is_img2img:
                send_text_button.click(fn=get_random_tags, inputs=[include_tags_textbox, exclude_tags_textbox], outputs=[self.img2img, url_textbox])
            else:
                send_text_button.click(fn=get_random_tags, inputs=[include_tags_textbox, exclude_tags_textbox], outputs=[self.text2img, url_textbox])

        return [send_text_button, include_tags_textbox, exclude_tags_textbox, url_textbox]

    def after_component(self, component, **kwargs):
        if kwargs.get("elem_id") == "txt2img_prompt":
            self.text2img = component

        if kwargs.get("elem_id") == "img2img_prompt":
            self.img2img = component