from bs4 import BeautifulSoup
import requests
import aiohttp
import asyncio
import re,json
import time

user_id = None
# 每个课程任一视频播放时的浏览器的url，用于获取课程所有video list
URL_2 = r"http://www.ehuixue.cn/video.aspx?cid=1426&vid=1429"
URL_1 = r"http://www.ehuixue.cn/video.aspx?cid=3641&vid=8516"

url_all_list = [URL_1, URL_2]

headers = {
    'Cookie': 'UM_distinctid=15b7a5fe3232a5-03462b997c05fb-396b4e08-100200-15b7a5fe3244c9; Z_LOCALE=1; ASP.NET_SessionId=zjt5uensj3sgm3woxbzbw15x; CNZZDATA1257656730=13003494-1492403576-%7C1494079622',
    "Content-Type": "application/json; charset=UTF-8",
}

index = 0

def get_all_video_url(url):
    video_list = []
    for i in url:
        r = requests.get(i, headers=headers).text
        video_list.extend(re.findall(r'(\?cid=\d+&vid=\d+)', r))
    return set(video_list)

async def watch_video(url):
    global user_id,index
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            rlt = await resp.text()
            bs = BeautifulSoup(rlt, 'lxml')
            if not user_id:
                user_id = bs.find(id='hidUserId')['value']
            course_id = bs.find(id='hidCourseId')['value']
            video_id = bs.find(id='hidVideoId')['value']
            study_id = bs.find(id='hidStudyId')['value']
            # m : _times
            m = re.findall(r"setLearn\('(.*?)', '1'\)", rlt)[0]
            data = {
                'c': course_id,
                'v': video_id,
                'm': m,
                'u': user_id,
                'o': '1',
                's': study_id
            }
            async with session.post('http://www.ehuixue.cn/Ajax/Do.aspx/DoStudy', data=json.dumps(data)) as r:
                print(await r.text()+ str(index))
            index += 1


if __name__ == '__main__':

    part_url = "http://www.ehuixue.cn/video.aspx"
    video_list = get_all_video_url(url_all_list)

    event_loop = asyncio.get_event_loop()
    tasks = [watch_video(part_url + i) for i in video_list]

    start = time.time()
    rlt = event_loop.run_until_complete(asyncio.wait(tasks))
    print('Time cost: {}'.format(time.time() - start))