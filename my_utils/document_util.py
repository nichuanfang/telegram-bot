""" 专门处理文档字节流的工具类 """

import io
import csv
import chardet
import pandas as pd
from docx import Document
import orjson
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
                parsed_json = orjson.loads(json_data)
                json_data = orjson.dumps(
                    parsed_json, option=orjson.OPT_INDENT_2).decode()
                return f'```{mime_type}\n{json_data}\n```'

            elif mime_type == 'application/xml' or mime_type == 'text/xml':  # 测试通过
                xml_root = ET.fromstring(raw_data)
                xml_text = ET.tostring(
                    xml_root, encoding='utf-8').decode('utf-8')
                return f'```{mime_type}\n{xml_text}\n```'

            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':  # docx测试通过
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

            else:
                try:
                    detected = chardet.detect(raw_data)
                    return f'```text/plain\n{raw_data.decode(detected["encoding"])}\n```'
                except:
                    raise RuntimeError('不支持的文档格式')

        except Exception as e:
            print(f"处理 MIME 类型 {mime_type} 出现异常: {e}")
            return ""
