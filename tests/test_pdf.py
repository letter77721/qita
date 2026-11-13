from agents.parser_agent import parse

def test_pdf_keeps_pages_and_detects_scanned_pages():
    import fitz
    with fitz.open() as doc:
        doc.new_page().insert_text((72,72),'Reynolds number')
        doc.new_page()
        pages=parse(doc.tobytes(),'slides.pdf')
    assert [p['number'] for p in pages]==[1,2]
    assert 'Reynolds' in pages[0]['text']
    assert pages[1]['status']=='needs_transcription'
