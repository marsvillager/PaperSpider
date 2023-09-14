import json
import os
import requests
import sys
import time

from pdf_tools import find_pdf, extract_group_pdf_content, extract_specified_pdf_title, extract_specified_pdf_content

# 获取当前模块所在的目录
current_dir = os.path.dirname(__file__)
# 获取根目录的路径
root_dir = os.path.abspath(os.path.join(current_dir, '..'))
# 将根目录添加到模块搜索路径中
sys.path.append(root_dir)
from log import logger


def chat_with_gpt(api_key: str, messages: str, proxy: dict[str, str]) -> json:
    """
    调用 chatgpt 3.5 api

    :param api_key: chatgpt 3.5 api
    :param messages: 问题
    :param proxy: 代理
    :return: 回答
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "user",
                "content": messages
            }
        ],
        "temperature": 0.7
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, proxies=proxy)
    if "choices" in response.json() and isinstance(response.json()["choices"], list) and len(
            response.json()["choices"]) > 0:  # choices 存在且为非空列表
        content: str = response.json()["choices"][0]["message"]["content"]
        logger.debug(f"Chatting...")
        return content
    else:  # choices 不存在或为空列表
        logger.error(f"ChatGPT has a processing error: {response.json()}")
        sys.exit()


def translate_abstract(api_key: str, content: str, proxy: dict[str, str]) -> json:
    """
    翻译论文摘要部分

    :param api_key: chatgpt 3.5 api
    :param content: 论文内容
    :param proxy: 代理
    :return: 翻译内容
    """
    abstract_content: str = extract_specified_pdf_content(content, 'Abstract', '1.')
    return chat_with_gpt(api_key, f'请结合自己的理解(作为备注放括号中)将下面内容翻译成中文: {abstract_content}', proxy)


def summarize_paper(api_key: str, contents: list, proxy: dict[str, str]) -> json:
    """
    概括论文

    :param api_key: chatgpt 3.5 api
    :param contents: 论文内容
    :param proxy: 代理
    :return: 论文概述
    """

    chat_with_gpt(api_key, f'我即将提交的文本将分为几个部分, 请等到所有部分都提供完之前即收到「end」标记前不用回复', proxy)
    for content in contents:
        # OpenAI GPT-3.5 Turbo 模型的请求速率限制(每分钟 3 个请求)
        time.sleep(20)

        chat_with_gpt(api_key, content, proxy)

    question: str = '用一长段话连贯地讲述上述论文的核心问题、主要贡献、解决方法等(中文表述)'
    return chat_with_gpt(api_key, f'「end」{question}', proxy)


if __name__ == '__main__':
    # proxy, 最好不直接用代理, 路由器接代理更不易察觉
    # ports: str = input("Please input the proxy port number(default is 1087): ") or '1087'
    proxies: dict[str, str] = {
        # 'http': f'http://127.0.0.1:{ports}',
        # 'https': f'http://127.0.0.1:{ports}'
    }
    # logger.info(f"Your proxy is http://127.0.0.1:{ports}")
    # time.sleep(0.5)

    # ChatGPT API key
    chatgpt: str = input("Please input the API Key of ChatGPT: ")
    logger.info(f"Your API key is <{chatgpt}>")
    time.sleep(0.5)

    # result path
    saved_path: str = input(
        "Please input the path to save results(default is ./sp_2023.json): ") or './sp_2023.json'
    logger.info(f"Saved path is <{saved_path}>")
    time.sleep(0.5)

    # paper path
    papers: str = input(
        "Please input the absolute path of papers: "
        "(If it's not a PDF file, then traverse the files in its subdirectories)\n")
    logger.info(f"Process <{papers}>")

    # process
    paper_list: list = []

    summary_papers: dict = {}  # summary of item_paper
    # 避免重复上传
    if os.path.exists(saved_path):
        with open(saved_path, "r", encoding='utf-8') as json_file:
            summary_papers = json.load(json_file)

    if os.path.splitext(papers)[1] == '.pdf':  # pdf 文件
        paper_list.append(papers)
    else:
        paper_list: list = find_pdf(papers)  # 目录
    for paper in paper_list:
        # 跳过已处理文件
        if paper in summary_papers:
            logger.warning(f'<{paper}> has already been processed.')
            continue

        item_paper: dict = {}  # title, abstract(self), abstract(gpt)

        paper_content: list = extract_group_pdf_content(paper, 2)

        if paper_content is None:
            # 保存已处理结果
            with open(saved_path, 'w', encoding='utf-8') as file:
                json.dump(summary_papers, file, indent=4, ensure_ascii=False)
            logger.info(f"Results saved to <{saved_path}>")
            sys.exit()

        logger.debug(f"Processing <{paper}> ...")

        item_paper['title'] = extract_specified_pdf_title(paper_content[0])

        # ChatGPT
        item_paper['abstract(gpt)'] = summarize_paper(chatgpt, paper_content, proxies)
        item_paper['abstract(paper)'] = translate_abstract(chatgpt, paper_content[0], proxies)

        summary_papers[paper] = item_paper

    with open(saved_path, 'w', encoding='utf-8') as file:
        json.dump(summary_papers, file, indent=4, ensure_ascii=False)
    logger.info(f"Results saved to <{saved_path}>")
