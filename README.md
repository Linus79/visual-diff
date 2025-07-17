# 🔥 Comparador Visual em Massa

Uma ferramenta em Python para automação de testes de regressão visual. O script descobre páginas de um site em produção, captura screenshots delas e de suas versões correspondentes em um ambiente de homologação, e gera um relatório HTML com comparações lado a lado destacando as diferenças visuais.

É a ferramenta ideal para garantir que novas implantações (deploys) não introduziram quebras ou alterações visuais inesperadas no layout.

---

## ✨ Funcionalidades Principais

-   **Descoberta Automática de Páginas:** Faz o crawling do site de produção para encontrar links e criar uma lista de páginas para comparação.
-   **Suporte a Sites Modernos:** Utiliza o **Playwright** para renderizar JavaScript, garantindo a captura de conteúdo em sites dinâmicos e SPAs (Single Page Applications).
-   **Comparação Inteligente de Imagens:** Usa a biblioteca **OpenCV** para analisar as duas imagens (produção vs. homologação) e calcular uma porcentagem de diferença visual.
-   **Relatório HTML Detalhado:** Cria um arquivo `relatorio.html` interativo com todas as comparações, links para as páginas, e o percentual de diferença para cada uma.

## ⚙️ Como Instalar e Configurar

Siga estes passos para preparar o ambiente e instalar todas as dependências necessárias.

### 1. Clonar o Repositório
Primeiro, clone o projeto para a sua máquina local.
```sh
git https://github.com/Linus79/visual-diff.git
cd visual-diff
```

### 2. Criar e Ativar um Ambiente Virtual
É uma prática essencial para isolar as dependências do projeto e evitar conflitos com pacotes do sistema.
```sh
# Crie o ambiente virtual
python3 -m venv venv

# Ative o ambiente
# No Linux ou macOS:
source venv/bin/activate
# No Windows:
.\venv\Scripts\activate
```

### 3. Instalar as Bibliotecas Python
Com o ambiente virtual ativo, instale todas as bibliotecas listadas no arquivo requirements.txt.
```sh
pip install -r requirements.txt
```

### 4. Instalar os Navegadores do Playwright
Esta é uma etapa obrigatória. O Playwright precisa dos navegadores (como Chromium, Firefox e WebKit) para poder controlá-los. Este comando baixa os arquivos necessários.
```sh
playwright install
```

### 5. Como Usar
Com tudo instalado, a execução é simples:
Execute o script principal:
```sh
python visual_diff.py
```