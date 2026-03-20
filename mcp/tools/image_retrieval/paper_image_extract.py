import time
from os import listdir
from os.path import isfile, join
from pathlib import Path
from docling_core.types.doc import PictureItem
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

IMAGE_RESOLUTION_SCALE = 2.0

def get_paper_figure(paper_path, output_dir):
    """
    Extract Figure using paper path and output to the output directory
    
    Args: 
        paper_path: directory path containing downloaded papers in pdf format
        output_dir: output directory path

    Returns:
        image saved at output directory

    Examples:
        get_paper_figure("./paper_folder", "./result")
    """
    papers = [join(paper_path, f) for f in listdir(paper_path) if isfile(join(paper_path, f))]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    #logging.basicConfig(level=logging.INFO)
    for file in papers:
        input_doc_path = file
    
        # Keep page/element images so they can be exported. The `images_scale` controls
        # the rendered image resolution (scale=1 ~ 72 DPI). The `generate_*` toggles
        # decide which elements are enriched with images.
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_picture_classification = True
        pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
        pipeline_options.generate_page_images = True
        pipeline_options.generate_picture_images = True
    
        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    
        start_time = time.time()
    
        conv_res = doc_converter.convert(input_doc_path)
        doc_filename = conv_res.input.file.stem
    
        # Save page images
        total_page_no = 0
        for page_no, page in conv_res.document.pages.items():
            total_page_no += 1
    
        if total_page_no > 2:
            #for page_no, page in conv_res.document.pages.items():
            #    page_no = page.page_no
            #    page_image_filename = output_dir / f"{doc_filename}-{page_no}.png"
            #    with page_image_filename.open("wb") as fp:
            #        page.image.pil_image.save(fp, format="PNG")
        
            # Save images of figures and tables
            table_counter = 0
            picture_counter = 0
            for element, _level in conv_res.document.iterate_items():
                #print(element)
                #if isinstance(element, TableItem):
                #    table_counter += 1
                #    element_image_filename = (
                #        output_dir / f"{doc_filename}-table-{table_counter}.png"
                #    )
                #    with element_image_filename.open("wb") as fp:
                #        element.get_image(conv_res.document).save(fp, "PNG")
        
                if isinstance(element, PictureItem):
                    if element.meta.classification.predictions[0].class_name != "icon" and element.meta.classification.predictions[0].class_name != "logo":
                        picture_counter += 1
                        element_image_filename = (
                            output_dir / f"{doc_filename}-picture-{picture_counter}.png"
                        )
                        with element_image_filename.open("wb") as fp:
                            element.get_image(conv_res.document).save(fp, "PNG")
        