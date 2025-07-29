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


# Carregar variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variáveis de ambiente carregadas do arquivo .env")
except ImportError:
    print("⚠️  python-dotenv não instalado. Execute: pip install python-dotenv")


class ApprovalTerminationStrategy(TerminationStrategy):
    """A strategy for determining when an agent should terminate."""
 
    async def should_agent_terminate(self, agent, history):
        """Check if the agent should terminate."""
        for message in reversed(history):
            if (
                message.role == AuthorRole.USER
                and "APPROVED" in message.content.upper()
            ):
                await self.on_approved_callback(agent, history)
                return True
        return False

    async def on_approved_callback(self, agent, history):
        """Executa ações após detecção de 'APPROVED'."""
        print("✅ Processo aprovado pelo usuário! Pós-processamento iniciado.")

        # Extrair o código HTML do histórico do SoftwareEngineer
        html_code = None
        html_pattern = r"```html\s*(.*?)```"
        for message in reversed(history):
            if hasattr(message, 'name') and message.name == "SoftwareEngineer":
                match = re.search(html_pattern, message.content, re.DOTALL | re.IGNORECASE)
                if match:
                    html_code = match.group(1).strip()
                    break

        if html_code:
            try:
                with open("index.html", "w", encoding="utf-8") as f:
                    f.write(html_code)
                print("📁 Arquivo index.html salvo com sucesso.")

                if not os.path.exists("push_to_git.sh"):
                    self.create_git_script()
                
                os.chmod("push_to_git.sh", 0o755)
                
                result = subprocess.run(["bash", "push_to_git.sh"], 
                                      capture_output=True, text=True, check=True)
                print("✅ Arquivo enviado para o repositório Git!")
                
            except Exception as e:
                print(f"❌ Erro: {e}")
        else:
            print("⚠️  Nenhum código HTML encontrado.")

    def create_git_script(self):
        """Cria o script push_to_git.sh se não existir."""
        # Obter o diretório onde o script Python está localizado
        script_dir = os.path.dirname(os.path.abspath(__file__))
        git_script_path = os.path.join(script_dir, "push_to_git.sh")
        
        script_content = '''#!/bin/bash
echo "🚀 Iniciando push para o repositório Git..."

if [ ! -d ".git" ]; then
    git init
    git config user.name "odl-user-1808301"
    git config user.email "odl_user_1808301@sandboxailabs1007.onmicrosoft.com"
fi

if [ ! -f "index.html" ]; then
    echo "❌ Erro: Arquivo index.html não encontrado."
    exit 1
fi

git add index.html
git commit -m "feat: Add generated HTML application - $(date '+%Y-%m-%d %H:%M:%S')"

if git remote get-url origin >/dev/null 2>&1; then
    git push origin main 2>/dev/null || git push origin master 2>/dev/null || {
        echo "⚠️  Push falhou. Arquivo commitado localmente."
    }
else
    echo "⚠️  Nenhum repositório remoto configurado."
    echo "Configure com: git remote add origin <URL_DO_SEU_REPOSITORIO>"
fi

echo "✅ Processo concluído!"
'''
        
        with open(git_script_path , "w", encoding="utf-8") as f:
            f.write(script_content)


# Define agent names
BusinessAnalyst_NAME = "BusinessAnalyst"
SoftwareEngineer_NAME = "SoftwareEngineer"
ProductOwner_NAME = "ProductOwner"

def create_kernel() -> Kernel:
    """Creates a Kernel instance with an Azure OpenAI ChatCompletion service."""
    kernel = Kernel()
    
    chat_deployment_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    try:
        kernel.add_service(service=AzureChatCompletion(
            deployment_name=chat_deployment_name,
            endpoint=endpoint,
            api_key=api_key
        ))
        
        print("✅ Kernel configurado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao configurar kernel: {e}")
        raise
    
    return kernel


async def run_multi_agent(input_text: str):
    """Implement the multi-agent system following the specified rules."""
    try:
        print("🔧 Criando kernel...")
        kernel = create_kernel()

        print("🤖 Criando agentes...")
        businessanalyst = ChatCompletionAgent(
            name=BusinessAnalyst_NAME,
            instructions=(
                "You are a Business Analyst. Take user requirements and create a detailed project plan "
                "for the requested app. Your analysis should be clear and actionable for the SoftwareEngineer "
                "and useful for the Product Owner to validate requirements."
            ),
            kernel=kernel,
        )

        softwareengineer = ChatCompletionAgent(
            name=SoftwareEngineer_NAME,
            instructions=(
                "You are a Software Engineer. Create a complete web app using HTML, CSS and JavaScript based on "
                "Business Analyst requirements. Always format your code using ```html [code] ``` "
                "for proper extraction. Include all CSS and JavaScript inline within the HTML. "
                "Implement all requested features completely and make it visually appealing."
            ),
            kernel=kernel,
        )

        productowner = ChatCompletionAgent(
            name=ProductOwner_NAME,
            instructions=(
                "You are the Product Owner. Review the Software Engineer's code to ensure all "
                "requirements are met. Verify the HTML code is properly formatted in ```html [code] ``` blocks. "
                "Test the logic and functionality conceptually. "
                "When satisfied with the implementation, respond with 'READY FOR USER APPROVAL'."
            ),
            kernel=kernel,
        )

        print("🔄 Configurando chat conforme as regras...")
        
        chat = AgentGroupChat(
            agents=[businessanalyst, softwareengineer, productowner],
            termination_strategy=ApprovalTerminationStrategy()
        )
        
        print("🤖 Sistema Multi-Agente configurado conforme as regras!")
        print("💡 O sistema pedirá sua aprovação quando pronto.")
        print("=" * 80)

        # Adicionar mensagem inicial do usuário
        user_message = ChatMessageContent(
            role=AuthorRole.USER,
            content=input_text
        )

        await chat.add_chat_message(user_message)

        # Variável para controlar estado
        pending_user_input = None
        conversation_active = True

        # Loop principal do chat
        while conversation_active:
            # Se temos input pendente, adicione primeiro
            if pending_user_input:
                print("💬 Enviando resposta do usuário...")
                
                # Aguardar um momento para garantir que o chat não está ativo
                await asyncio.sleep(0.5)
                
                # Verificar se ainda está ativo e aguardar mais se necessário
                max_retries = 10
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        approval_message = ChatMessageContent(
                            role=AuthorRole.USER,
                            content=pending_user_input
                        )
                        await chat.add_chat_message(approval_message)
                        print("✅ Mensagem enviada com sucesso!")
                        break
                    except Exception as e:
                        if "Unable to proceed while another agent is active" in str(e):
                            retry_count += 1
                            print(f"⏳ Aguardando chat ficar disponível (tentativa {retry_count}/{max_retries})...")
                            await asyncio.sleep(1.0)
                        else:
                            raise e
                else:
                    print("❌ Não foi possível enviar mensagem após várias tentativas.")
                    break
                
                # Se foi aprovação, esta será a última rodada
                is_final_round = (pending_user_input == "APPROVED")
                pending_user_input = None
                
                # Processar a resposta
                async for content in chat.invoke():
                    agent_name = getattr(content, 'name', 'Unknown')
                    print(f"\n🤖 {content.role} - {agent_name}:")
                    print(f"💬 {content.content}")
                    print("-" * 80)
                
                # Se foi aprovação, terminar
                if is_final_round:
                    conversation_active = False
                    
            else:
                # Processar conversa normal
                messages_count = 0
                async for content in chat.invoke():
                    agent_name = getattr(content, 'name', 'Unknown')
                    print(f"\n🤖 {content.role} - {agent_name}:")
                    print(f"💬 {content.content}")
                    print("-" * 80)
                    messages_count += 1
                    
                    # Checa se o ProductOwner pediu aprovação do usuário
                    if (
                        content.role == AuthorRole.ASSISTANT
                        and agent_name == ProductOwner_NAME
                        and "READY FOR USER APPROVAL" in content.content.upper()
                    ):
                        print("\n🎯 Produto pronto para aprovação!")
                        
                        while True:
                            user_input = input("✋ Digite 'APPROVED' para aprovar ou 'REJECTED' para revisar: ").strip().upper()
                            
                            if user_input == "APPROVED":
                                pending_user_input = "APPROVED"
                                print("✅ Aprovação confirmada! Aguardando processamento...")
                                break
                            elif user_input == "REJECTED":
                                revision_request = input("💬 Descreva as mudanças necessárias: ")
                                pending_user_input = f"REJECTED: {revision_request}. Please revise the implementation according to these requirements."
                                print("🔄 Feedback registrado! Aguardando processamento...")
                                break
                            else:
                                print("⚠️ Resposta inválida. Digite 'APPROVED' ou 'REJECTED'.")
                        
                        # Sair deste loop de chat
                        break
                
                # Se não houve mensagens e não há input pendente, conversa terminou
                if messages_count == 0 and not pending_user_input:
                    conversation_active = False
                
        print("\n🎉 Processo finalizado!")
                    
    except Exception as e:
        print(f"❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(run_multi_agent(
            "Quero um app de calculadora simples com operações básicas (+, -, *, /) "
            "e interface moderna com botões grandes e cores atrativas."
        ))
    except KeyboardInterrupt:
        print("\n👋 Processo interrompido pelo usuário.")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()