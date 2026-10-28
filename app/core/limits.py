"""Bound request bodies before multipart parsing can spool unbounded files."""
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self,app,max_bytes):
        self.app,self.max_bytes=app,max_bytes

    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] not in {"POST","PUT","PATCH","DELETE"}:
            return await self.app(scope,receive,send)
        chunks=[]
        size=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect": return
            size+=len(message.get("body",b""))
            if size>self.max_bytes:
                return await JSONResponse({"detail":"Request exceeds upload limit"},status_code=413)(scope,receive,send)
            chunks.append(message)
            if not message.get("more_body",False): break
        position=0
        async def bounded_receive():
            nonlocal position
            if position<len(chunks):
                message=chunks[position]
                position+=1
                return message
            return await receive()
        await self.app(scope,bounded_receive,send)
