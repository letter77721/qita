from pathlib import Path


def parse(data, filename):
    suffix = Path(filename).suffix.lower()
    if suffix in ('.txt', '.md'):
        return [{'number':1, 'text':data.decode('utf-8-sig'), 'status':'extracted'}]
    if suffix == '.pdf':
        import fitz
        with fitz.open(stream=data, filetype='pdf') as doc:
            if doc.needs_pass:
                raise ValueError('请先解除 PDF 密码保护')
            if len(doc) > 150:
                raise ValueError('单个 PDF 最多 150 页，请拆分后上传')
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text(sort=True).strip()
                pages.append({'number':i+1,'text':text,'status':'extracted' if text else 'needs_ocr'})
            return pages
    if suffix in ('.png','.jpg','.jpeg'):
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(data)) as im:
            im.verify()
        return [{'number':1,'text':'','status':'needs_ocr'}]
    raise ValueError('不支持的文件格式')
