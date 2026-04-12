# vanna_setup.py
import os
from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, User, RequestContext
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService

load_dotenv()

GROUPS = ["user"]


class DefaultUserResolver(UserResolver):
    async def resolve_user(self, context: RequestContext) -> User:
        return User(id="clinic_user", email="user@clinic.local",
                    group_memberships=GROUPS)


def build_memory() -> DemoAgentMemory:
    """Returns a fresh DemoAgentMemory instance — seed directly into this."""
    return DemoAgentMemory(max_items=1000)


def create_agent(memory: DemoAgentMemory = None) -> Agent:
    llm = OpenAILlmService(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
    )

    runner = SqliteRunner(database_path="clinic.db")

    tools = ToolRegistry()
    tools.register_local_tool(RunSqlTool(sql_runner=runner),    access_groups=GROUPS)
    tools.register_local_tool(VisualizeDataTool(),              access_groups=GROUPS)
    tools.register_local_tool(SaveQuestionToolArgsTool(),       access_groups=GROUPS)
    tools.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=GROUPS)

    agent_memory = memory if memory is not None else build_memory()

    return Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        config=AgentConfig(),
        agent_memory=agent_memory,
    )