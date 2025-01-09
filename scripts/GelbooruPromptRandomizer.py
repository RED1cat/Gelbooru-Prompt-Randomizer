import contextlib

import gradio as gr
from modules import scripts, shared, script_callbacks

from scripts.Gel import Gelbooru

async def get_random_tags(include, exclude, current_prompt):
    include = include.replace(" ", "")
    exclude = exclude.replace(" ", "")
    api_key = getattr(shared.opts, "gpr_api_key", None)
    user_id = getattr(shared.opts, "gpr_user_id", None)

    if(include == ""):
        include = None
    else:
        include = include.split(',')

    if(exclude == ""):
        exclude = None
    else:
        exclude = exclude.split(',')

    if(api_key == "" or api_key == None or user_id == "" or user_id == None or getattr(shared.opts, "gpr_anonymous_user", True)):
        api_key = None
        user_id = None

    gel_post = await Gelbooru(api_key=api_key, user_id=user_id).random_post(tags=include, exclude_tags=exclude)

    if(gel_post == None or gel_post == []):
        return current_prompt, "Couldn't find a post with the specified tags"
    
    tags = gel_post.get_tags()
    for id in range(len(tags)):
        if(tags[id] not in getattr(shared.opts, "gpr_undersocreReplacementExclusionList").split(',')):
            tags[id] = tags[id].replace("_", " ")

    return ', '.join(tags), gel_post

class GPRScript(scripts.Script):
    
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
                send_text_button.click(fn=get_random_tags, inputs=[include_tags_textbox, exclude_tags_textbox, self.img2img], outputs=[self.img2img, url_textbox])
            else:
                send_text_button.click(fn=get_random_tags, inputs=[include_tags_textbox, exclude_tags_textbox, self.text2img], outputs=[self.text2img, url_textbox])

        return [send_text_button, include_tags_textbox, exclude_tags_textbox, url_textbox]
    
    def on_ui_settings():
        GPR_SECTION = ("gpr", "Gelbooru Prompt Randomizer")

        gpr_options = {
            "gpr_anonymous_user": shared.OptionInfo(True, "Anonymous", gr.Checkbox),
            "gpr_api_key": shared.OptionInfo("", "api_key", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_user_id": shared.OptionInfo("", "user_id", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            #Taken from a1111-sd-webui-tagcomplete
            "gpr_replaceUnderscores": shared.OptionInfo(True, "Replace underscores with spaces on insertion"),
            "gpr_undersocreReplacementExclusionList": shared.OptionInfo("0_0,(o)_(o),+_+,+_-,._.,<o>_<o>,<|>_<|>,=_=,>_<,3_3,6_9,>_o,@_@,^_^,o_o,u_u,x_x,|_|,||_||", "Underscore replacement exclusion list").info("Add tags that shouldn't have underscores replaced with spaces, separated by comma."),
        }

        for key, opt, in gpr_options.items():
            opt.section = GPR_SECTION
            shared.opts.add_option(key, opt)

    script_callbacks.on_ui_settings(on_ui_settings)

    def after_component(self, component, **kwargs):
        if kwargs.get("elem_id") == "txt2img_prompt":
            self.text2img = component

        if kwargs.get("elem_id") == "img2img_prompt":
            self.img2img = component