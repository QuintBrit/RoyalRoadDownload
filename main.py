import os
import subprocess
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import aiofiles

'''
TODO:
handle cover
fix table of contents
fix A/Ns
Add emailing options
make into terminal app
'''

VALID_FILE_FORMATS = ["azw3", "docx", "epub", "fb2", "htmlz", "lit", "lrf", "mobi", "odt", "pdb", "pdf", "pml", "rb",
                      "rtf", "snb", "tcr", "txt", "txtz"]


async def get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


async def get_fictions_from_profile(profile_url):
    html = await get(profile_url+"/fictions")
    soup = BeautifulSoup(html, 'html.parser')
    fictions = soup.find_all('a', class_='btn btn-default btn-outline')
    fiction_links = []
    for fiction in fictions:
        print(fiction["href"])
        fiction_links.append(fiction["href"])
    return fiction_links


async def get_favourites_from_profile(profile_url):
    html = await get(profile_url + "/favorites")
    soup = BeautifulSoup(html, 'html.parser')
    fictions = soup.find_all('a', class_='btn btn-default btn-outline')
    fiction_links = []
    for fiction in fictions:
        fiction_links.append("https://www.royalroad.com"+fiction["href"])
    return fiction_links


async def mass_download_fictions(mode, file_formats, paths, files, fictions=[], profile=""):
    fiction_links = fictions
    if mode == "favourites":
        fiction_links = await get_favourites_from_profile(profile)
    elif mode == "fictions":
        fiction_links = await get_fictions_from_profile(profile)

    for i in range(len(fiction_links)):
        if type(file_formats) != list:
            if type(paths) != list:
                await download_story(fiction_links[i], paths, files, file_formats)
            else:
                await download_story(fiction_links[i], paths[i], files[i], file_formats)


async def get_chapter_text(chapter_url):
    html = await get(chapter_url)
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1', class_='font-white', style='margin-top: 10px')
    print(title.text)
    title = str(title).replace('<h1 class="font-white"', '<h1 class="chapter"')
    note = soup.find('div', class_='portlet-body author-note')
    if note is not None:
        note = str(note).replace('<div class="spoiler" data-class="spoiler" data-caption="Spoiler">', ">! ")
        note = note.replace('<td style="width: 98.6971%">', '<td style="width: 98.6971%; background-color: #00436e">')
        note = note.replace('<td style="width: 98.4211%">', '<td style="width: 98.4211%; background-color: #00436e">')

    text = str(soup.find_all("div", class_="chapter-inner chapter-content")[0])
    text = text.replace('<div class="spoiler" data-class="spoiler" data-caption="Spoiler">', ">! ")
    text = text.replace("<p> </p>", "")
    text = text.replace('<td style="width: 99.1477%">', '<td style="width: 98.1477%; background-color: #00436e">')
    text = text.replace('<td style="width: 99.1477%; text-align: center">', '<td style="width: 98.6971%; text-align: center; background-color: #00436e">')
    text = text.replace('<td style="width: 98.6971%">', '<td style="width: 98.6971%; background-color: #00436e">')

    return text, note, title


async def get_chapter_html(chapter_url):
    return await get(chapter_url)


async def get_next_chapter_url(chapter_url):
    html = await get(chapter_url)
    soup = BeautifulSoup(html, 'html.parser')
    try:
        next_link = soup.find_all('a', class_='btn btn-primary col-xs-12')[1]
    except IndexError:
        print("First or last chapter")
        next_link = soup.find_all('a', class_='btn btn-primary col-xs-12')[0]
        if next_link.text.strip() == "Previous Chapter":
            return None

    try:
        return "https://royalroad.com" + next_link['href']
    except IndexError:
        print("no more chaps")
        return None


async def get_first_chapter_url(story_url):
    html = await get(story_url)
    soup = BeautifulSoup(html, 'html.parser')
    first_chapter = soup.find('a', class_='btn btn-lg btn-primary')
    return "https://royalroad.com" + first_chapter['href']


async def get_metadata(story_url):
    html = await get(story_url)
    soup = BeautifulSoup(html, 'html.parser')
    author = soup.find('h4', property='author').text.replace("by ", "").strip().split("\n")[0]
    description = soup.find('div', class_='description').text.replace("\n", " ").strip()
    cover_url = soup.find('img', class_='thumbnail inline-block')["src"].split("?")[0]
    title = soup.find('h1', property='name').text
    return [author, description, cover_url, title]


async def get_css(url, path):
    html = await get(url)
    soup = BeautifulSoup(html, "html.parser")
    css_files = []
    for css in soup.find_all("link", rel="stylesheet"):
        css_files.append("https://www.royalroad.com/"+css["href"])

    css_code_files = []
    for css in css_files:
        if "fonts" in css:
            file = "fonts.css"
        else:
            file = css.split("/")[-1].split("?")[0]
        css_code_files.append(file)

        async with aiofiles.open(path+"\\"+file, "a+", encoding="utf-8") as f:
            css_code = await get(css)
            await f.write(css_code)

    return css_code_files


async def file_writer(chapter_url, file, ending):
    async with aiofiles.open(file+ending, "a+", encoding="utf-8") as f:
        text, note, title = await get_chapter_text(chapter_url)
        await f.write(title)
        if note is not None:
            await f.write(note)
        await f.write(text)


async def get_whole_story(story_url, file_name, mode="md"):
    next_url = await get_first_chapter_url(story_url)
    while next_url is not None:
        if mode == "md":
            await file_writer(next_url, file_name, ".md")
        elif mode == "ebook":
            await file_writer(next_url, file_name, ".html")
        next_url = await get_next_chapter_url(next_url)


async def convert_to_file(path, file, format, metadata):
    if format not in VALID_FILE_FORMATS:
        print("Invalid file format")
    else:
        print(f"Converting to .{format}")
        author, description, cover, title = metadata
        subprocess.run(["C:\\Program Files\\Calibre2\\ebook-convert.exe",
                        path+"\\"+file+".html",
                        path+"\\"+file+"."+format,
                        "--title="+title,
                        '--cover='+cover,
                        '--remove-first-image',
                        '--comments="'+description+'"',
                        "--authors="+author,
                        ],
                       shell=True)


async def download_story(story_url, path, file, format):
    print(f"Downloading story: {story_url}")
    await get_whole_story(story_url, path, mode="ebook")
    await convert_to_file(path, file, format, metadata=await get_metadata(story_url))


async def email(path, email):
    pass


async def test(story_url):
    # html = await get(story_url)
    # soup = BeautifulSoup(html, 'html.parser')
    # author = soup.find('h4', property='author').text.replace("by ", "").strip()
    # description = soup.find('div', class_='description').text.replace("\n", " ").strip()
    # cover_url = soup.find('img', class_='thumbnail inline-block')["src"].split("?")[0]
    await download_story(story_url, "C:\\Users\\Tom-User\\Downloads\\Royal_road_downloads\\bluecore", "blue_core", "mobi")
    await convert_to_file("C:\\Users\\Tom-User\\Downloads\\Royal_road_downloads\\bluecore", "blue_core", "mobi", metadata=await get_metadata(story_url))


asyncio.run(test(
    "https://www.royalroad.com/fiction/25082/blue-core",
))
