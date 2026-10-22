"""Generate distributable icon format and portable manual from project assets."""
from pathlib import Path
from PIL import Image
from manual import html_document


if __name__=='__main__':
    assets=Path(__file__).resolve().parent/'assets'
    with Image.open(assets/'RestorationLab.png') as image:
        image.save(assets/'RestorationLab.icns',format='ICNS')
    (assets/'User_Guide.html').write_text(html_document(),encoding='utf-8')
    print('Prepared macOS icon and standalone user guide.')
