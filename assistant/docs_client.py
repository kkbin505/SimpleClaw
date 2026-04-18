import logging
from googleapiclient.discovery import build
from google_auth import get_credentials

logger = logging.getLogger(__name__)

class GoogleDocsClient:
    def __init__(self):
        self.drive_service = build("drive", "v3", credentials=get_credentials())
        self.docs_service = build("docs", "v1", credentials=get_credentials())

    def list_shared_docs(self, keywords=None):
        """
        列出分享给我且标题包含关键词的 Google Docs
        """
        query = "mimeType = 'application/vnd.google-apps.document' and trashed = false"
        
        logger.info("Searching for shared Google Docs...")
        results = self.drive_service.files().list(
            q=query,
            pageSize=50,
            fields="nextPageToken, files(id, name, owners)"
        ).execute()
        
        items = results.get("files", [])
        logger.info(f"Drive API found {len(items)} documents.")
        for item in items:
            logger.debug(f"  - Found doc: {item['name']} ({item['id']})")
        
        if keywords:
            filtered_items = []
            for item in items:
                name = item.get("name", "")
                if any(kw.lower() in name.lower() for kw in keywords):
                    filtered_items.append(item)
            return filtered_items
            
        return items

    def get_doc_text(self, doc_id):
        """
        获取 Google Doc 的纯文本内容
        """
        try:
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            content = doc.get('body').get('content')
            return self._read_structural_elements(content)
        except Exception as e:
            logger.error(f"Error reading document {doc_id}: {e}")
            raise e

    def _read_structural_elements(self, elements):
        """
        递归解析文档结构元素并提取文本
        """
        text = ""
        for value in elements:
            if 'paragraph' in value:
                elements = value.get('paragraph').get('elements')
                for elem in elements:
                    text += self._read_paragraph_element(elem)
            elif 'table' in value:
                table = value.get('table')
                for row in table.get('tableRows'):
                    cells = row.get('tableCells')
                    for cell in cells:
                        text += self._read_structural_elements(cell.get('content'))
            elif 'tableOfContents' in value:
                toc = value.get('tableOfContents')
                text += self._read_structural_elements(toc.get('content'))
        return text

    def _read_paragraph_element(self, element):
        """
        解析段落元素
        """
        text_run = element.get('textRun')
        if not text_run:
            return ""
        return text_run.get('content')
