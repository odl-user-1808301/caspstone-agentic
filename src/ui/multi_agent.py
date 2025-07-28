import os
import asyncio
import subprocess
import re

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.agents.strategies.selection.kernel_function_selection_strategy import (
    KernelFunctionSelectionStrategy,
)
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import AzureChatCompletion
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel



class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""
 
    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        for message in reversed(history):
            if (message.role == AuthorRole.USER and
                message.content.upper() in "APPROVED"
            ):
                return True
        return False


async def run_multi_agent(input: str):
    """implement the multi-agent system."""

    Kernel = Kernel()
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    service = AzureChatCompletion(
        deployment_name=deployment,
        endpoint=endpoint,
        api_key=key,
    )
    # Defina as personas
    personas = [
        {
            "name": "BusinessAnalyst",
            "system_prompt": (
                "You are a Business Analyst which will take the requirements from the user (also known as a 'customer') "
                "and create a project plan for creating the requested app. The Business Analyst understands the user requirements "
                "and creates detailed documents with requirements and costing. The documents should be usable by the SoftwareEngineer "
                "as a reference for implementing the required features, and by the Product Owner for reference to determine if the "
                "application delivered by the Software Engineer meets all of the user's requirements."
            ),
        },
        {
            "name": "SoftwareEngineer",
            "system_prompt": (
                "You are a Software Engineer, and your goal is create a web app using HTML and JavaScript by taking into consideration "
                "all the requirements given by the Business Analyst. The application should implement all the requested features. "
                "Deliver the code to the Product Owner for review when completed. You can also ask questions of the BusinessAnalyst to clarify any requirements that are unclear."
            ),
        },
        {
            "name": "ProductOwner",
            "system_prompt": (
                "You are the Product Owner which will review the software engineer's code to ensure all user requirements are completed. "
                "You are the guardian of quality, ensuring the final product meets all specifications. IMPORTANT: Verify that the Software Engineer has shared the HTML code using the format ```html [code] ```. "
                "This format is required for the code to be saved and pushed to GitHub. Once all client requirements are completed and the code is properly formatted, reply with 'READY FOR USER APPROVAL'. "
                "If there are missing features or formatting issues, you will need to send a request back to the SoftwareEngineer or BusinessAnalyst with details of the defect."
            ),
        },
    ]

    # Crie os agentes
    agents = [
        ChatCompletionAgent(
            name=persona["name"],
            system_message=persona["system_prompt"],
            kernel=Kernel,
            service=service,
        )
        for persona in personas
    ]

    # Crie o grupo de agentes
    group = AgentGroupChat(
        agents=agents,
        selection_strategy=KernelFunctionSelectionStrategy(),
        termination_strategy=ApprovalTerminationStrategy(),
    )

    # Inicie a conversa
    history = [ChatMessageContent(
        author_role=AuthorRole.USER,
        content=input,
    )]

    # Loop de interação entre agentesc
    approved = False
    while True:
        response = await group.step(history)
        history.append(response)
        # Verifica se algum agente quer terminar
        if await group.termination_strategy.should_agent_terminate(group, history):
            approved = True
            break

    # Pós-processamento: se aprovado, extraia e salve o HTML, faça push
    if approved:
        html_code = None
        # Procura pelo código HTML no histórico
        html_pattern = r"```html\s*([\s\S]+?)```"
        for msg in history:
            if msg.author_role == AuthorRole.AGENT and msg.author_name == "SoftwareEngineer":
                match = re.search(html_pattern, msg.content)
                if match:
                    html_code = match.group(1).strip()
                    break

        if html_code:
            # Salva o HTML em index.html
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_code)

            # Executa o script de push
            script_path = os.path.join(os.path.dirname(__file__), "push_to_git.sh")
            subprocess.run(["bash", script_path, "index.html"], check=True)

        # Retorne todas as respostas para análise
        responses = [msg.content for msg in history if msg.author_role != AuthorRole.USER]
    return responses