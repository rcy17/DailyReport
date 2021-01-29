import asyncio
from pyppeteer import launcher
from datetime import datetime, timedelta
from random import random
from argparse import ArgumentParser
from time import sleep


def patch_pyppeteer():
    """
    This function is copied from https://github.com/miyakogi/pyppeteer/pull/160#issuecomment-448886155
    This is a bug about chromium, and here is a simple method to temporarily fix it
    """
    import pyppeteer.connection
    original_method = pyppeteer.connection.websockets.client.connect

    def new_method(*args, **kwargs):
        kwargs['ping_interval'] = None
        kwargs['ping_timeout'] = None
        return original_method(*args, **kwargs)

    pyppeteer.connection.websockets.client.connect = new_method


async def login(page):
    await page.goto('https://thos.tsinghua.edu.cn/')
    await page.type('#i_user', username)
    await page.type('#i_pass', password)
    await page.waitFor(100)
    await page.click('.btn')
    await page.waitFor(2000)
    element = await page.querySelector("#msg_note")
    error = await page.evaluate('(element) => Boolean(element)', element)
    if error:
        raise ValueError('帐号或密码错误！')
    await page.waitForSelector(".box[name='学生健康及出行情况报告']")


async def check_committed(page):
    """Check if today we have already committed"""
    await page.goto('https://thos.tsinghua.edu.cn/fp/view?m=fp#act=fp/myserviceapply/indexFinish')
    await page.waitForSelector('.apply-detail-outside')
    details = await page.querySelector('.apply-detail-outside')
    element = await details.querySelector('li')
    content = await page.evaluate('(element) => element.textContent', element)
    dt = datetime.strptime(content[5:], '%Y-%m-%d %H:%M:%S')
    return dt.date() == datetime.now().date()


async def commit(page):
    await page.goto(
        'https://thos.tsinghua.edu.cn/fp/view?m=fp#from=hall&'
        'serveID=b44e2daf-0ef6-4d11-a115-0eb0d397934f&act=fp/serveapply')
    await page.waitForSelector('#formIframe')
    frames = page.frames
    for frame in frames:
        if frame.name == 'formIframe':
            break
    else:
        raise ValueError('未找到frame: formIframe,文件结构可能已改变!请到 https://github.com/rcy17/DailyReport 提一个issue～')
    wait_seconds = 0
    while True:
        if wait_seconds > 30:
            raise Exception('30s内未加载完成，已自动退出(请确定您此前提交过该表，因此详细地址非空)')
        await page.waitFor(1000)
        element = await page.querySelector('#layui-layer-shade1')
        if element:
            # remove the shade layer
            _ = await page.evaluate('document.getElementById("layui-layer-shade1").remove()')
        element = await frame.querySelector('#MQXXSZ')
        content = await frame.evaluate('(element) => { return element && element.value }', element)
        if content:
            break
        await page.waitFor(1000)
        wait_seconds += 1
    await page.waitFor(500)
    await page.click('#commit')
    await page.waitForNavigation()
    await page.waitFor(1000)


async def process():
    browser = await launcher.launch(args=['--no-sandbox', '--disable-setuid-sandbox'])
    try:
        page = await browser.newPage()
        await login(page)
        is_committed = await check_committed(page)
        if not is_committed:
            await commit(page)
            is_committed = await check_committed(page)
            if not is_committed:
                raise Exception('本次打卡失败')
            print('今日打卡成功')
        else:
            print('(今天已经打卡过了)')
    finally:
        await browser.close()


def parse_arguments():
    parser = ArgumentParser()
    parser.add_argument('-u', '--username', type=str, required=True)
    parser.add_argument('-p', '--password', type=str, required=True)
    parser.add_argument('-i', '--interval', type=int, default=180, help='在7:00 + [0, interval]分钟的随机偏移时刻打卡')
    return parser.parse_args()


def main():
    next_time = datetime.now()
    while True:
        current = datetime.now()
        if current < next_time:
            sleep(60)
            continue
        try:
            asyncio.run(process())
        except Exception as e:
            print(datetime.now(), type(e), e)
            if isinstance(e, ValueError):
                break
            sleep(10)
            continue
        current = datetime.now()
        tomorrow = (current + timedelta(days=1)).replace(hour=7, minute=0, second=0)
        next_time = tomorrow + timedelta(minutes=(random() * arguments.interval))
        print('计划下次打卡时间：', next_time)


if __name__ == '__main__':
    patch_pyppeteer()
    arguments = parse_arguments()
    username = arguments.username
    password = arguments.password
    main()
