import os


def search_files(root_dir, keyword):
    count = 0
    print(f"正在搜索 {root_dir} 下的文件包含关键字 {keyword}")
    file_count = 0
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_count += 1
            if keyword.lower() in file.lower():
                print(os.path.join(root, file))
                count += 1
    print(f"共查询到{file_count}个文件，其中包含关键字 {keyword} 的文件有 {count} 个")


def main():
    root_directory = input("请输入要搜索的根目录（默认为当前目录，请直接回车）：")
    if not root_directory:
        root_directory = '.'
    search_keyword = input("请输入要搜索的关键字：")
    search_files(root_directory, search_keyword)


if __name__ == "__main__":
    main()
