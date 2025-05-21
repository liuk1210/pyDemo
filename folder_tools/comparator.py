import hashlib
import os
import sys
import tempfile
import threading
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import LiteralString


class TreeNode:
    def __init__(self, name):
        self.name = name
        self.children = OrderedDict()
        self.original_path = ""

    def get_original_path(self):
        return self.original_path

    def get_compressed_name(self):
        path = [self.name]
        current = self
        full_path = self.original_path
        while len(current.children) == 1:
            child = next(iter(current.children.values()))
            path.append(child.name)
            if child.original_path:
                full_path = child.original_path
            current = child
        self.original_path = full_path
        return "/".join(path)

    def get_actual_children(self):
        current = self
        while len(current.children) == 1:
            child = next(iter(current.children.values()))
            if child.original_path:
                self.original_path = child.original_path
            current = child
        return current.children

    @classmethod
    def build_file_tree(cls, paths):
        if not paths:
            return None
        normalized_paths = sorted([p.replace("\\", "/") for p in paths])
        root = TreeNode("")
        for path in normalized_paths:
            parts = path.split("/")
            current = root
            for part in parts:
                if part not in current.children:
                    current.children[part] = TreeNode(part)
                current = current.children[part]
            current.original_path = path
        return root


class HtmlFileTreePrinter:
    HTML_TEMPLATE = r"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>%s</title>
                <style>
                    * {
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    }

                    html, body {
                        height: 100%%;
                        overflow: hidden;
                    }

                    body {
                        background-color: #ededed;
                        color: #000000;
                    }

                    .container {
                        height: 100%%;
                        max-width: 800px;
                        margin: 0 auto;
                        background: #fff;
                        display: flex;
                        flex-direction: column;
                    }

                    .header {
                        padding: 20px;
                        background: #fff;
                        border-bottom: 1px solid #e6e6e6;
                        flex-shrink: 0;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    }

                    .title {
                        font-size: 18px;
                        font-weight: bold;
                        color: #333;
                    }

                    .search-wrapper {
                        width: 300px;
                    }

                    .search-box {
                        background: #f5f5f5;
                        border-radius: 4px;
                        padding: 8px 12px;
                        display: flex;
                        align-items: center;
                    }

                    .search-box input {
                        border: none;
                        background: transparent;
                        width: 100%%;
                        outline: none;
                        margin-left: 8px;
                        font-size: 14px;
                    }

                    .search-icon {
                        color: #888;
                        font-size: 14px;
                    }

                    .tree-container {
                        flex: 1;
                        overflow-y: auto;
                        padding: 10px 0;
                    }

                    .tree-item {
                        padding: 12px 20px;
                        display: flex;
                        align-items: center;
                        cursor: pointer;
                        transition: background-color 0.2s;
                    }

                    .tree-item:hover {
                        background-color: #f5f5f5;
                    }

                    .tree-item:active {
                        background-color: #f0f0f0;
                    }

                    .tree-item i {
                        margin-right: 10px;
                        color: #07c160;
                    }

                    .tree-item.file i {
                        color: #888;
                    }

                    .tree-item span {
                        font-size: 14px;
                        color: #333;
                    }

                    .tree-content {
                        margin-left: 20px;
                        border-left: 1px solid #f0f0f0;
                    }

                    .hidden {
                        display: none;
                    }

                    .arrow {
                        display: inline-block;
                        width: 8px;
                        height: 8px;
                        border-right: 2px solid #888;
                        border-bottom: 2px solid #888;
                        transform: rotate(-45deg);
                        margin-right: 10px;
                        transition: transform 0.2s;
                    }

                    .arrow.expanded {
                        transform: rotate(45deg);
                    }

                    .no-results {
                        padding: 20px;
                        text-align: center;
                        color: #888;
                        font-size: 14px;
                        display: none;
                    }

                    .status-bar {
                        padding: 10px 20px;
                        background: #f9f9f9;
                        border-top: 1px solid #e6e6e6;
                        color: #666;
                        font-size: 12px;
                        flex-shrink: 0;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    }

                    .base-path-select {
                        padding: 4px 8px;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        font-size: 12px;
                        outline: none;
                        background: #fff;
                        max-width: 300px;
                    }

                    .base-path-select option {
                        font-size: 12px;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="title">%s</div>
                        <div class="search-wrapper">
                            <div class="search-box">
                                <span class="search-icon">🔍</span>
                                <input type="text" id="searchInput" placeholder="搜索">
                            </div>
                        </div>
                    </div>
                    <div class="tree-container" id="fileTree">
                        %s
                    </div>
                    <div class="no-results">
                        未找到相关内容
                    </div>
                    <div class="status-bar">
                        <div>
                            总计: <span id="totalCount">0</span> 项 |
                            当前显示: <span id="visibleCount">0</span> 项
                        </div>
                        <select class="base-path-select" id="basePathSelect">
                            %s
                        </select>
                    </div>
                </div>

                <script>
                    document.addEventListener('DOMContentLoaded', function() {
                        // 初始化时隐藏所有子目录（第一层除外）
                        document.querySelectorAll('.tree-content').forEach(content => {
                            const level = getLevel(content);
                            if (level > 1) {
                                content.classList.add('hidden');
                            }
                        });

                        // 获取元素的层级
                        function getLevel(element) {
                            let level = 0;
                            let current = element;
                            while (current && !current.id.includes('fileTree')) {
                                if (current.classList.contains('tree-content')) {
                                    level++;
                                }
                                current = current.parentElement;
                            }
                            return level;
                        }

                        // 获取节点的完整路径
                        function getNodePath(element) {
                            const parts = [];
                            let current = element;
                            while (current && !current.id.includes('fileTree')) {
                                if (current.classList.contains('tree-item')) {
                                    const nameSpan = current.querySelector('span:not(.arrow)');
                                    if (nameSpan) {
                                        parts.unshift(nameSpan.textContent);
                                    }
                                }
                                current = current.parentElement;
                            }
                            return parts.join('/');
                        }

                        // 处理文件点击
                        document.querySelectorAll('.tree-item.file').forEach(item => {
                            item.addEventListener('click', function(e) {
                                e.stopPropagation();
                                const basePath = document.getElementById('basePathSelect').value;
                                const relativePath = this.getAttribute('data-path');
                                if (relativePath) {
                                    const fullPath = basePath + '/' + relativePath;
                                    window.open('file:///' + fullPath.replace(/\\/g, '/'), '_blank');
                                }
                            });
                        });

                        // 处理文件夹点击
                        document.querySelectorAll('.tree-item:not(.file)').forEach(item => {
                            item.addEventListener('click', function(e) {
                                e.stopPropagation();
                                const content = this.nextElementSibling;
                                if (content && content.classList.contains('tree-content')) {
                                    content.classList.toggle('hidden');
                                    const arrow = this.querySelector('.arrow');
                                    if (arrow) {
                                        arrow.classList.toggle('expanded');
                                    }
                                }
                            });
                        });

                        // 更新计数
                        function updateCounts() {
                            const total = document.querySelectorAll('.tree-item').length;
                            const visible = document.querySelectorAll('.tree-item:not([style*="display: none"])').length;
                            document.getElementById('totalCount').textContent = total;
                            document.getElementById('visibleCount').textContent = visible;
                        }

                        // 初始计数
                        updateCounts();

                        // 搜索功能
                        const searchInput = document.getElementById('searchInput');
                        const noResults = document.querySelector('.no-results');

                        searchInput.addEventListener('input', function() {
                            const searchText = this.value.toLowerCase();
                            let hasResults = false;

                            document.querySelectorAll('.tree-item').forEach(item => {
                                const itemText = item.textContent.toLowerCase();
                                const shouldShow = itemText.includes(searchText);

                                if (shouldShow) {
                                    hasResults = true;
                                    item.style.display = '';
                                    let parent = item.parentElement;
                                    while (parent && parent.classList.contains('tree-content')) {
                                        parent.classList.remove('hidden');
                                        parent = parent.parentElement;
                                    }
                                } else {
                                    item.style.display = 'none';
                                }
                            });

                            noResults.style.display = hasResults ? 'none' : 'block';
                            updateCounts();
                        });
                    });
                </script>
            </body>
            </html>
    """

    @classmethod
    def print(cls, paths, base_paths, title):
        root = TreeNode.build_file_tree(paths)
        if not root:
            return
        base_options = cls.generate_base_path_options(base_paths)
        html_content = cls.generate_html_tree(root, base_options, title)
        output_file = cls.write_html_file(html_content)
        cls.open_in_browser(output_file)

    @staticmethod
    def generate_base_path_options(base_paths):
        if not base_paths:
            return ""
        return "\n".join(
            f'<option value="{path.replace("\\", "/")}">{path.replace("\\", "/")}</option>'
            for path in base_paths
        )

    @classmethod
    def generate_html_tree(cls, node, base_options, title):
        sb = []
        cls.generate_html_tree_content(node, sb)
        return cls.HTML_TEMPLATE % (title, title, "".join(sb), base_options)

    @classmethod
    def generate_html_tree_content(cls, node, sb):
        if not node.name:
            for child in node.children.values():
                cls.generate_html_tree_content(child, sb)
            return
        display_name = node.get_compressed_name()
        has_children = bool(node.get_actual_children())
        sb.append(f'<div class="tree-item{" file" if not has_children else ""}" '
                  f'data-path="{node.get_original_path()}">')
        if has_children:
            sb.append('<span class="arrow"></span>')
        sb.append(f'<i>{"📁" if has_children else "📄"}</i>')
        sb.append(f'<span>{display_name}</span></div>')
        if has_children:
            sb.append('<div class="tree-content">')
            for child in node.get_actual_children().values():
                cls.generate_html_tree_content(child, sb)
            sb.append('</div>')

    @staticmethod
    def write_html_file(content):
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".html", delete=False
            ) as f:
                f.write(content)
                return f.name
        except Exception as e:
            raise RuntimeError("生成HTML文件失败") from e

    @staticmethod
    def open_in_browser(file_path):
        try:
            webbrowser.open(f"file://{os.path.abspath(file_path)}")
        except Exception as e:
            raise RuntimeError("打开浏览器失败") from e


class FolderComparator:
    @staticmethod
    def compare_folders(path1, path2, compare_sha256):
        if not os.path.exists(path1):
            print(f"{path1}不存在")
            return
        if not os.path.exists(path2):
            print(f"{path2}不存在")
            return
        base_path1 = os.path.normpath(path1)
        base_path2 = os.path.normpath(path2)
        same_path_files, diff_info = FolderComparator.collect_file_differences(base_path1, base_path2)
        if compare_sha256:
            FolderComparator.compare_files_in_parallel(same_path_files, base_path1, base_path2)
        print("文件夹比对结束")

    @staticmethod
    def collect_file_differences(base_path1: LiteralString, base_path2: LiteralString):
        lock = threading.Lock()
        same_path_files = []
        diff_info = {
            "1_not_in_2_folder": [],
            "2_not_in_1_folder": [],
            "1_not_in_2_file": [],
            "2_not_in_1_file": []
        }

        def walk_directory(base_path: LiteralString, other_base: LiteralString, folder_list, file_list, append_same):

            for root, dirs, files in os.walk(base_path):
                relative = os.path.relpath(root, base_path)
                if relative == ".":
                    relative = ""
                target = os.path.join(other_base, relative)
                if not os.path.exists(target):
                    with lock:
                        folder_list.append(relative)
                    dirs[:] = []  # 跳过子目录
                    continue
                for file in files:
                    rel_path = os.path.join(relative, file) if relative else file
                    target_file = os.path.join(other_base, rel_path)
                    if not os.path.exists(target_file):
                        with lock:
                            file_list.append(rel_path)
                    else:
                        with lock:
                            if append_same:
                                same_path_files.append(rel_path)

        print(f"正在读取{base_path1}并收集{base_path2}缺失的文件中...")
        walk_directory(base_path1, base_path2, diff_info["1_not_in_2_folder"], diff_info["1_not_in_2_file"], True)
        FolderComparator.print_diff_info(base_path2, diff_info["1_not_in_2_folder"],
                                         diff_info["1_not_in_2_file"])
        print(f"正在读取{base_path2}并收集{base_path1}缺失的文件中...")
        walk_directory(base_path2, base_path1, diff_info["2_not_in_1_folder"], diff_info["2_not_in_1_file"], False)
        FolderComparator.print_diff_info(base_path1, diff_info["2_not_in_1_folder"],
                                         diff_info["2_not_in_1_file"])
        return same_path_files, diff_info

    @staticmethod
    def print_diff_info(base_path2, missing_folders, missing_files):
        all_missing = missing_folders + missing_files
        if not all_missing:
            print(f"读取文件完毕，{base_path2}中不存在文件/文件夹缺失。")
            return
        print(f"读取文件完毕，{base_path2}中缺失{len(all_missing)}个文件/文件夹（详情见弹出的html）。")
        HtmlFileTreePrinter.print(all_missing, [base_path2], f"{base_path2}中缺失的文件/文件夹")

    @staticmethod
    def compare_files_in_parallel(common_files, base_path1, base_path2):
        if not common_files:
            return
        total_files = len(common_files)
        processed = 0
        lock = threading.Lock()
        results = []
        progress_lock = threading.Lock()

        def process_file(rel_path):
            nonlocal processed
            path1 = os.path.join(base_path1, rel_path)
            path2 = os.path.join(base_path2, rel_path)
            hash1 = calculate_sha256(path1)
            hash2 = calculate_sha256(path2)
            with lock:
                if hash1 != hash2:
                    results.append(rel_path)
                processed += 1
                with progress_lock:
                    progress = processed / total_files * 100
                    sys.stdout.write(f"\r正在计算并比对sha256中，进度: {processed}/{total_files} ({progress:.2f}%)")
                    sys.stdout.flush()

            return hash1 != hash2

        with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            futures = [executor.submit(process_file, rel_path) for rel_path in common_files]
            for _ in as_completed(futures):
                pass  # 结果已通过回调处理
        print(f"\n计算并比对文件sha256结束，存在{len(results)}个文件sha256不一致")
        if results:
            HtmlFileTreePrinter.print(results, [base_path1, base_path2], "SHA256不一致的文件")


def calculate_sha256(file_path):
    if not os.path.isfile(file_path):
        return ""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(1024 * 1024)  # 1MB chunk
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


if __name__ == "__main__":
    folder1 = input(r"请输入源文件夹路径（默认为D:\Workspaces）：")
    if folder1.strip() == "":
        folder1 = r"D:\Workspaces"
    folder2 = input(r"请输入需要对比的文件夹路径（默认为V:\Workspaces）：")
    if folder2.strip() == "":
        folder2 = r"V:\Workspaces"
    is_compare_sha256 = True
    str3 = input("是否比对文件sha256(默认为比对，输入N时不比对)：")
    if str3.strip() == "N":
        is_compare_sha256 = False
    FolderComparator.compare_folders(folder1, folder2, is_compare_sha256)
