import asyncio
import httpx

async def main():
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        payload = {"session_id": "665061d3-1430-49dc-8913-5de1399a806b", "query": "ขั้นตอนการทำบัตรประชาชนใหม่"}
        response = await client.post("http://203.154.130.166/dopa/chat", json=payload)
        print(response.text)

if __name__ == "__main__":
    asyncio.run(main())