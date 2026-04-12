# test_agent.py
import asyncio
from vanna.core.user import RequestContext, User
from vanna_setup import create_agent

agent  = create_agent()
user    = User(id="clinic_user", email="user@clinic.local")
context = RequestContext(user=user)

async def main():
    question = "How many patients do we have?"
    print("QUESTION:", question)
    async for component in agent.send_message(
        request_context=context,
        message=question,
    ):
        print(" ", component)

asyncio.run(main())