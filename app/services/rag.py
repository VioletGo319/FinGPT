# app/services/rag.py
def search_and_answer(question: str, k: int = 5):
    # TODO: 1) 检索 2) 拼装上下文 3) LLM 生成 + 引用
    return "answer", [{"doc":"...","chunk_id":1}]