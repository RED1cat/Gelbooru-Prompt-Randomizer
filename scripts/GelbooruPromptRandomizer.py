import contextlib
import io

import aiohttp
import gradio as gr
from PIL import Image
from modules import scripts, shared, script_callbacks

from scripts.Gel import Gelbooru


async def _fetch_image(url):
    if not url:
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://gelbooru.com/",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                data = await response.read()
        return Image.open(io.BytesIO(data))
    except Exception:
        return None

async def get_random_tags(include, exclude):
    include = include.replace(" ", "")
    exclude = exclude.replace(" ", "")
    api_key = getattr(shared.opts, "gpr_api_key", None)
    user_id = getattr(shared.opts, "gpr_user_id", None)
    display_all_content = getattr(shared.opts, "gpr_displayAllContent", True)

    if(api_key == "" or user_id == ""):
        return "You need to log in to your gelbooru account", None, "You need to log in to your gelbooru account"

    if(include == ""):
        include = None
    else:
        include = include.split(',')

    if(exclude == ""):
        exclude = None
    else:
        exclude = exclude.split(',')

    blacklist_raw = getattr(shared.opts, "gpr_universalBlacklist", "") or ""
    blacklist = [t.strip().lower().replace(" ", "_") for t in blacklist_raw.split(',') if t.strip()]
    if blacklist:
        exclude = (exclude or []) + blacklist

    gel_post = await Gelbooru(api_key=api_key, user_id=user_id, display_all_content=display_all_content).random_post(tags=include, exclude_tags=exclude)

    if(gel_post == None or gel_post == []):
        return "Couldn't find a post with the specified tags", None, "Couldn't find a post with the specified tags"

    tags = gel_post.get_tags()
    if blacklist:
        blacklist_set = set(blacklist)
        tags = [t for t in tags if t.lower() not in blacklist_set]
    for id in range(len(tags)):
        if(tags[id] not in getattr(shared.opts, "gpr_undersocreReplacementExclusionList").split(',')):
            tags[id] = tags[id].replace("_", " ")


    image = await _fetch_image(gel_post.file_url)

    return ', '.join(tags), image, str(gel_post)

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
                include_tags_textbox = gr.Textbox(label='Include Tags', placeholder="es: 1girl, blue_hair, solo")
                exclude_tags_textbox = gr.Textbox(label='Exclude Tags', placeholder="es: nsfw, text, watermark")

                with gr.Row():
                    send_text_button = gr.Button(value='Randomize', variant='primary', size='sm')
                    clear_button = gr.Button(value='Clear', size='sm')

                result_tags_textbox = gr.Textbox(label='Tags', show_copy_button=True, interactive=False)
                
                with gr.Row():
                    replace_tags_button = gr.Button(value='Replace Tags', variant='primary', size='sm')
                    append_tags_button = gr.Button(value='Append Tags', size='sm')

                preview_image = gr.Image(interactive=False, show_label=False, height=400)

                url_textbox = gr.Textbox(label='Post URL', show_copy_button=True, interactive=False)

        with contextlib.suppress(AttributeError):
            replace_tags_button.click(fn=lambda result_tags:(result_tags), inputs=result_tags_textbox, outputs=self.text2img if not is_img2img else self.img2img)
            append_tags_button.click(fn=lambda result_tags, tags:(f"{tags}, {result_tags}"), inputs=[result_tags_textbox, self.text2img if not is_img2img else self.img2img], outputs=self.text2img if not is_img2img else self.img2img)
            send_text_button.click(fn=get_random_tags, inputs=[include_tags_textbox, exclude_tags_textbox], outputs=[result_tags_textbox, preview_image, url_textbox])
            clear_button.click(fn=lambda:(None, None, None), inputs=None, outputs=[preview_image, url_textbox, result_tags_textbox])

        return [include_tags_textbox, exclude_tags_textbox, send_text_button, clear_button, result_tags_textbox, replace_tags_button, append_tags_button, preview_image, url_textbox]
    
    def on_ui_settings():
        GPR_SECTION = ("gpr", "Gelbooru Prompt Randomizer")

        gpr_options = {
            "gpr_api_key": shared.OptionInfo("", "api_key", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_user_id": shared.OptionInfo("", "user_id", gr.Textbox).info("<a href=\"https://gelbooru.com/index.php?page=account&s=options\" target=\"_blank\">Account Options</a>"),
            "gpr_displayAllContent": shared.OptionInfo(True, "Display all site content").info("Enable Gelbooru's 'Display all site content' option."),
            # Taken from a1111-sd-webui-tagcomplete
            "gpr_replaceUnderscores": shared.OptionInfo(True, "Replace underscores with spaces on insertion"),
            "gpr_undersocreReplacementExclusionList": shared.OptionInfo("0_0,(o)_(o),+_+,+_-,._.,<o>_<o>,<|>_<|>,=_=,>_<,3_3,6_9,>_o,@_@,^_^,o_o,u_u,x_x,|_|,||_||", "Underscore replacement exclusion list").info("Add tags that shouldn't have underscores replaced with spaces, separated by comma."),
            "gpr_universalBlacklist": shared.OptionInfo("", "Universal tag blacklist").info("Tags listed here are always excluded from results and stripped from the returned tag list, in addition to the per-run Exclude Tags. Separate with commas (e.g. nsfw, text, watermark)."),
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
