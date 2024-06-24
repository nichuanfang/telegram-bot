""" 专门处理文档字节流的工具类 """

import io
import csv
import tempfile
import chardet
import pandas as pd
import pptx
from docx import Document
import fitz  # PyMuPDF 库，用于处理 PDF
import json
import xml.etree.ElementTree as ET  # 处理 XML


class DocumentHandler:

    @staticmethod
    def format(raw_data: bytes, mime_type: str) -> str:
        """
        格式化给定的原始数据根据 MIME 类型为文本形式。

        Parameters:
        - raw_data (bytes): 原始数据的字节流
        - mime_type (str): MIME 类型字符串

        Returns:
        - str: 格式化后的文本内容
        """
        try:
            if mime_type == 'text/plain' or mime_type == 'text/markdown' or mime_type == 'text/html':  # 测试通过
                return f'```{mime_type}\n{raw_data.decode("utf-8")}\n```'

            elif mime_type == 'text/csv':  # 测试通过
                detected = chardet.detect(raw_data)
                csv_data = raw_data.decode(detected['encoding'])
                text = ""
                reader = csv.reader(io.StringIO(csv_data))
                for row in reader:
                    text += ', '.join(row) + "\n"
                return f'```{mime_type}\n{text}\n```'

            elif mime_type == 'application/json':  # 测试通过
                json_data = raw_data.decode('utf-8')
                parsed_json = json.loads(json_data)
                json_data = json.dumps(
                    parsed_json, indent=4, ensure_ascii=False)
                return f'```{mime_type}\n{json_data}\n```'

            elif mime_type == 'application/xml' or mime_type == 'text/xml':  # 测试通过
                xml_root = ET.fromstring(raw_data)
                xml_text = ET.tostring(
                    xml_root, encoding='utf-8').decode('utf-8')
                return f'```{mime_type}\n{xml_text}\n```'

            elif mime_type == 'application/msword' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':  # doc测试未通过   docx测试通过
                docx_file = io.BytesIO(raw_data)
                doc = Document(docx_file)
                text = ""
                for para in doc.paragraphs:
                    text += para.text + "\n"
                return f'```text/plain\n{text}\n```'

            elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mime_type == 'application/vnd.ms-excel':  # xls和xtls均测试通过
                # xls  xlxs
                excel_data = io.BytesIO(raw_data)
                excel_file = pd.ExcelFile(excel_data)
                text = ""
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    text += df.to_string(index=False) + "\n\n"
                return f'```{mime_type}\n{text}\n```'

            elif mime_type == 'application/pdf':  # 测试未通过
                # pdf
                pdf_data = io.BytesIO(raw_data)
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix='.pdf')
                temp_file.write(pdf_data.getvalue())
                temp_file.close()

                pdf_text = ""
                with fitz.open(temp_file.name) as pdf:
                    for page_num in range(len(pdf)):
                        page = pdf.load_page(page_num)
                        pdf_text += page.get_text()
                return f'```{mime_type}\n{pdf_text}\n```'

            elif mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or mime_type == 'application/vnd.ms-powerpoint':  # 测试未通过
                # ppt
                ppt_data = io.BytesIO(raw_data)
                ppt_file = pptx.Presentation(ppt_data)
                text = ""
                for slide in ppt_file.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, 'text'):
                            text += shape.text + "\n"
                return f'```{mime_type}\n{text}\n```'

            else:
                try:
                    detected = chardet.detect(raw_data)
                    return f'```text/plain\n{raw_data.decode(detected["encoding"])}\n```'
                except:
                    raise RuntimeError('不支持的文档格式')

        except Exception as e:
            print(f"处理 MIME 类型 {mime_type} 出现异常: {e}")
            return ""


if __name__ == "__main__":
    # 示例用法，假设有一个 JSON 文件的字节流 json_bytes
    json_bytes = b'{"name": "John", "age": 30, "city": "New York"}'
    formatted_text = DocumentHandler.format(json_bytes, 'application/json')
    print(formatted_text)

    # 示例用法，假设有一个 XML 文件的字节流 xml_bytes
    xml_bytes = b'<note><to>Tove</to><from>Jani</from><heading>Reminder</heading><body>Don\'t forget me this weekend!</body></note>'
    formatted_text = DocumentHandler.format(xml_bytes, 'application/xml')
    print(formatted_text)
