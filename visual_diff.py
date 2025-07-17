import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import cv2
import numpy as np
import os
from datetime import datetime
import time
import re

class BulkVisualComparator:
    def __init__(self, prod_domain, hml_domain, max_pages=20):
        self.prod_domain = prod_domain.replace('https://', '').replace('http://', '')
        self.hml_domain = hml_domain.replace('https://', '').replace('http://', '')
        self.max_pages = max_pages
        self.found_urls = set()
        self.results_dir = f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Detecta protocolos de cada domínio independentemente
        self.prod_protocol = self.detect_protocol(self.prod_domain)
        self.hml_protocol = self.detect_protocol(self.hml_domain)
        
        print(f"🔗 Protocolo PRODUÇÃO: {self.prod_protocol.upper()}")
        print(f"🔗 Protocolo HOMOLOGAÇÃO: {self.hml_protocol.upper()}")
        
        # Cria diretório para resultados
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(f"{self.results_dir}/screenshots", exist_ok=True)
        os.makedirs(f"{self.results_dir}/comparisons", exist_ok=True)
        
    def detect_protocol(self, domain):
        """Detecta se o domínio usa HTTP ou HTTPS"""
        # Primeiro tenta HTTPS
        try:
            response = requests.get(f"https://{domain}", timeout=10, verify=False)
            if response.status_code == 200:
                return "https"
        except:
            pass
        
        # Se HTTPS falhar, tenta HTTP
        try:
            response = requests.get(f"http://{domain}", timeout=10)
            if response.status_code == 200:
                return "http"
        except:
            pass
        
        # Se ambos falharem, assume HTTPS como padrão
        return "https"
        
    # (Dentro da classe BulkVisualComparator)

    def discover_pages(self, browser): # <<-- RECEBE O NAVEGADOR
        """Descobre páginas do site automaticamente usando Playwright para lidar com JS."""
        print(f"🔍 Descobrindo páginas em {self.prod_domain}...")

        base_url = f"{self.prod_protocol}://{self.prod_domain}"
        pages_to_visit = [base_url]
        visited = set()

        # O bloco "with sync_playwright()" FOI REMOVIDO DAQUI
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        while len(self.found_urls) < self.max_pages and pages_to_visit:
            current_url = pages_to_visit.pop(0)

            if current_url in visited:
                continue

            visited.add(current_url)
            # Remove a hashtag e tudo que vem depois para evitar duplicatas (ex: /pagina#main)
            clean_url = current_url.split('#')[0]

            try:
                # Verifica se a URL limpa (sem a âncora) já foi adicionada
                if clean_url in self.found_urls:
                    continue
                
                print(f"  Analisando: {current_url}")
                page.goto(current_url, wait_until='networkidle', timeout=30000)
                self.found_urls.add(clean_url)

                links = page.eval_on_selector_all('a[href]', 'elements => elements.map(el => el.href)')

                for link in links:
                    full_url = urljoin(current_url, link)
                    parsed = urlparse(full_url)
                    
                    # Normaliza a URL para evitar duplicatas como http://site.com e http://site.com/
                    normalized_url = full_url.split('#')[0].rstrip('/')

                    if (parsed.netloc.endswith(self.prod_domain) and
                        normalized_url not in visited and
                        normalized_url not in pages_to_visit and
                        not any(ext in full_url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.css', '.js'])):
                        
                        pages_to_visit.append(normalized_url)
                        
                        if len(self.found_urls) >= self.max_pages:
                            break

            except Exception as e:
                print(f"  ❌ Erro ao acessar {current_url}: {e}")
                continue
        
        page.close()
        context.close()
        # O "browser.close()" FOI REMOVIDO DAQUI
        print(f"✅ Encontradas {len(self.found_urls)} páginas para comparar")
        return list(self.found_urls)
    
    # (Dentro da classe BulkVisualComparator)

    def capture_screenshot(self, browser, url, filename):
        """Captura screenshot de uma página com fallback HTTP/HTTPS"""
        original_url = url
        
        # Se a URL não tem protocolo, detecta automaticamente
        if not url.startswith(('http://', 'https://')):
            domain = url
            protocol = self.detect_protocol(domain)
            url = f"{protocol}://{domain}"
        
        # Lista de URLs para tentar (protocolo original e fallback)
        urls_to_try = [url]
        
        # Adiciona fallback se não funcionou
        if url.startswith('https://'):
            urls_to_try.append(url.replace('https://', 'http://'))
        elif url.startswith('http://'):
            urls_to_try.append(url.replace('http://', 'https://'))
        
        for attempt_url in urls_to_try:
            context = None  # Inicializa o contexto como None
            page = None     # Inicializa a page como None
            try:
                print(f"    🔗 Tentando: {attempt_url}")
                
                # Não usa mais 'with sync_playwright()'. Usa o 'browser' recebido.
                context = browser.new_context(
                    ignore_https_errors=True,
                    viewport={'width': 1200, 'height': 800}
                )
                
                page = context.new_page()
                
                page.goto(attempt_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(2000)
                
                # Scroll automático
                page.evaluate("""
                    () => {
                        return new Promise((resolve) => {
                            let totalHeight = 0;
                            let distance = 100;
                            let timer = setInterval(() => {
                                let scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;

                                if(totalHeight >= scrollHeight){
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 50);
                        });
                    }
                """)
                
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(1000)
                
                page.screenshot(path=filename, full_page=True)
                
                # Fecha apenas a página e o contexto
                page.close()
                context.close()
                
                print(f"    ✅ Screenshot capturado com sucesso: {attempt_url}")
                return True
                
            except Exception as e:
                print(f"    ⚠️  Erro com {attempt_url}: {e}")
                # Garante que os recursos sejam fechados em caso de erro
                if page and not page.is_closed():
                    page.close()
                if context:
                    context.close()
                continue
        
        print(f"    ❌ Falha em todas as tentativas para {original_url}")
        return False
    
    def create_side_by_side_comparison(self, prod_img_path, hml_img_path, output_path, page_name):
        """Cria comparação lado a lado"""
        try:
            # Carrega imagens
            prod_img = cv2.imread(prod_img_path)
            hml_img = cv2.imread(hml_img_path)
            
            if prod_img is None or hml_img is None:
                print(f"    ❌ Erro ao carregar imagens para {page_name}")
                return False
            
            # Redimensiona para mesma altura
            max_height = max(prod_img.shape[0], hml_img.shape[0])
            
            # Calcula proporções para manter aspect ratio
            prod_ratio = prod_img.shape[1] / prod_img.shape[0]
            hml_ratio = hml_img.shape[1] / hml_img.shape[0]
            
            prod_width = int(max_height * prod_ratio)
            hml_width = int(max_height * hml_ratio)
            
            prod_resized = cv2.resize(prod_img, (prod_width, max_height))
            hml_resized = cv2.resize(hml_img, (hml_width, max_height))
            
            # Calcula diferença para destacar mudanças
            if prod_resized.shape == hml_resized.shape:
                diff = cv2.absdiff(prod_resized, hml_resized)
                gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
                diff_pixels = np.sum(thresh > 0)
                total_pixels = prod_resized.shape[0] * prod_resized.shape[1]
                diff_percentage = (diff_pixels / total_pixels) * 100
            else:
                diff_percentage = 100  # Tamanhos diferentes = 100% diferente
            
            # Cria espaço entre as imagens
            separator = np.ones((max_height, 20, 3), dtype=np.uint8) * 128
            
            # Junta as imagens lado a lado
            comparison = np.hstack([prod_resized, separator, hml_resized])
            
            # Adiciona cabeçalho com informações
            header_height = 80
            header = np.ones((header_height, comparison.shape[1], 3), dtype=np.uint8) * 50
            
            # Adiciona texto no cabeçalho
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            thickness = 2
            
            # Título da página
            cv2.putText(header, f"PAGINA: {page_name}", (10, 25), font, font_scale, (255, 255, 255), thickness)
            
            # Labels das colunas
            cv2.putText(header, "PRODUCAO", (10, 55), font, font_scale, (0, 255, 0), thickness)
            hml_x = prod_width + 30
            cv2.putText(header, "HOMOLOGACAO", (hml_x, 55), font, font_scale, (0, 100, 255), thickness)
            
            # Porcentagem de diferença
            diff_color = (0, 0, 255) if diff_percentage > 5 else (0, 255, 0)
            diff_x = comparison.shape[1] - 300
            cv2.putText(header, f"DIFF: {diff_percentage:.1f}%", (diff_x, 40), font, font_scale, diff_color, thickness)
            
            # Junta cabeçalho com comparação
            final_image = np.vstack([header, comparison])
            
            # Salva resultado
            cv2.imwrite(output_path, final_image)
            return diff_percentage
            
        except Exception as e:
            print(f"    ❌ Erro ao criar comparação para {page_name}: {e}")
            return None
    
    # (Dentro da classe BulkVisualComparator)

    def run_comparison(self):
        """Executa a comparação completa"""
        print(f"🚀 Iniciando comparação: {self.prod_domain} vs {self.hml_domain}")

        # Cria os diretórios de resultados de forma segura
        screenshots_dir = os.path.join(self.results_dir, 'screenshots')
        comparisons_dir = os.path.join(self.results_dir, 'comparisons')
        os.makedirs(screenshots_dir, exist_ok=True)
        os.makedirs(comparisons_dir, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            pages = self.discover_pages(browser)
            
            if not pages:
                print("❌ Nenhuma página encontrada!")
                browser.close()
                return
            
            results = []
            total_pages = len(pages)
            
            for i, prod_url in enumerate(pages, 1):
                parsed_prod = urlparse(prod_url)
                
                hml_url = f"{self.hml_protocol}://{self.hml_domain}{parsed_prod.path}"
                if parsed_prod.query:
                    hml_url += f"?{parsed_prod.query}"
                
                page_path = parsed_prod.path.strip('/').replace('/', '_')
                if not page_path:
                    page_path = 'home'
                page_name = f"{page_path}_{i:02d}"
                
                print(f"\n📄 [{i}/{total_pages}] Processando: {page_name}")
                print(f"  PROD: {prod_url}")
                print(f"  HML:  {hml_url}")
                
                # --- MUDANÇA PRINCIPAL AQUI ---
                # Usa os.path.join para criar os caminhos dos arquivos
                prod_screenshot = os.path.join(screenshots_dir, f"prod_{page_name}.png")
                hml_screenshot = os.path.join(screenshots_dir, f"hml_{page_name}.png")
                comparison_path = os.path.join(comparisons_dir, f"{page_name}_comparison.png")
                
                print("  📸 Capturando produção...")
                prod_success = self.capture_screenshot(browser, prod_url, prod_screenshot)
                
                print("  📸 Capturando homologação...")
                hml_success = self.capture_screenshot(browser, hml_url, hml_screenshot)
                
                if prod_success and hml_success:
                    print("  🔄 Criando comparação...")
                    diff_percentage = self.create_side_by_side_comparison(
                        prod_screenshot, hml_screenshot, comparison_path, page_name
                    )
                    
                    results.append({
                        'page': page_name,
                        'prod_url': prod_url,
                        'hml_url': hml_url,
                        'diff_percentage': diff_percentage,
                        'success': True
                    })
                    print(f"  ✅ Concluído - Diferença: {diff_percentage:.1f}%")
                else:
                    results.append({
                        'page': page_name,
                        'prod_url': prod_url,
                        'hml_url': hml_url,
                        'diff_percentage': None,
                        'success': False
                    })
                    print(f"  ❌ Falhou")
                
                time.sleep(1)
            
            # Fecha o navegador no final de tudo
            browser.close()
        
        self.generate_report(results)
        
        print(f"\n🎉 Comparação concluída!")
        print(f"📁 Resultados salvos em: {self.results_dir}")
    
    def generate_report(self, results):
        """Gera relatório HTML dos resultados"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Relatório de Comparação Visual</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
                .result {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .success {{ border-left: 5px solid #4CAF50; }}
                .error {{ border-left: 5px solid #f44336; }}
                .high-diff {{ border-left: 5px solid #ff9800; }}
                .comparison-img {{ max-width: 100%; margin: 10px 0; }}
                .stats {{ display: flex; gap: 20px; margin: 10px 0; }}
                .stat {{ background: #e3f2fd; padding: 10px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Comparação Visual: {self.prod_domain} vs {self.hml_domain}</h1>
                <p><strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                <p><strong>Total de páginas:</strong> {len(results)}</p>
            </div>
        """
        
        # Estatísticas
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        high_diff = [r for r in successful if r['diff_percentage'] and r['diff_percentage'] > 10]
        
        html_content += f"""
            <div class="stats">
                <div class="stat">
                    <strong>Sucessos:</strong> {len(successful)}
                </div>
                <div class="stat">
                    <strong>Falhas:</strong> {len(failed)}
                </div>
                <div class="stat">
                    <strong>Grandes diferenças (>10%):</strong> {len(high_diff)}
                </div>
            </div>
        """
        
        # Resultados individuais
        for result in results:
            if result['success']:
                diff = result['diff_percentage']
                css_class = 'high-diff' if diff and diff > 10 else 'success'
                
                html_content += f"""
                    <div class="result {css_class}">
                        <h3>{result['page']}</h3>
                        <p><strong>Diferença:</strong> {diff:.1f}%</p>
                        <p><strong>Produção:</strong> <a href="{result['prod_url']}" target="_blank">{result['prod_url']}</a></p>
                        <p><strong>Homologação:</strong> <a href="{result['hml_url']}" target="_blank">{result['hml_url']}</a></p>
                        <img src="comparisons/{result['page']}_comparison.png" class="comparison-img" alt="{result['page']} comparison">
                    </div>
                """
            else:
                html_content += f"""
                    <div class="result error">
                        <h3>{result['page']} - ERRO</h3>
                        <p><strong>Produção:</strong> {result['prod_url']}</p>
                        <p><strong>Homologação:</strong> {result['hml_url']}</p>
                        <p>Falha ao capturar screenshots</p>
                    </div>
                """
        
        html_content += """
        </body>
        </html>
        """
        
        # Salva relatório
        report_path = os.path.join(self.results_dir, "relatorio.html")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

def get_user_input():
    """Solicita os domínios do usuário com validação"""
    print("🌐 CONFIGURAÇÃO DOS DOMÍNIOS")
    print("=" * 50)
    
    while True:
        print("\nDigite os domínios que deseja comparar:")
        print("Exemplo: teste.com.br ou https://teste.com.br ou teste.com.br:8080")
        print()
        
        prod_domain = input("🟢 Domínio de PRODUÇÃO: ").strip()
        if not prod_domain:
            print("❌ Domínio de produção não pode estar vazio!")
            continue
            
        hml_domain = input("🟡 Domínio de HOMOLOGAÇÃO: ").strip()
        if not hml_domain:
            print("❌ Domínio de homologação não pode estar vazio!")
            continue
        
        # Remove protocolos se existirem
        prod_clean = prod_domain.replace('https://', '').replace('http://', '')
        hml_clean = hml_domain.replace('https://', '').replace('http://', '')
        
        print(f"\n📋 CONFIGURAÇÃO:")
        print(f"   Produção:    {prod_clean}")
        print(f"   Homologação: {hml_clean}")
        print("   (Protocolo será detectado automaticamente)")
        
        while True:
            confirm = input("\n✅ Confirma essa configuração? (s/n): ").lower().strip()
            if confirm in ['s', 'sim', 'y', 'yes']:
                return prod_clean, hml_clean
            elif confirm in ['n', 'não', 'nao', 'no']:
                break
            else:
                print("Por favor, digite 's' para sim ou 'n' para não.")
                
def get_max_pages():
    """Solicita número máximo de páginas"""
    while True:
        try:
            max_pages = input("\n📄 Quantas páginas deseja comparar? (padrão: 20): ").strip()
            if not max_pages:
                return 20
            
            max_pages = int(max_pages)
            if max_pages <= 0:
                print("❌ Número deve ser maior que zero!")
                continue
            elif max_pages > 100:
                print("⚠️  Muitas páginas podem demorar bastante. Recomendamos máximo 50.")
                confirm = input("Deseja continuar mesmo assim? (s/n): ").lower().strip()
                if confirm not in ['s', 'sim', 'y', 'yes']:
                    continue
            
            return max_pages
            
        except ValueError:
            print("❌ Por favor, digite um número válido!")

# Uso da aplicação
if __name__ == "__main__":
    print("=" * 60)
    print("🔥 COMPARADOR VISUAL EM MASSA")
    print("=" * 60)
    
    try:
        # Solicita dados do usuário
        prod_domain, hml_domain = get_user_input()
        max_pages = get_max_pages()
        
        print(f"\n🚀 Iniciando comparação...")
        print(f"   📊 Máximo de páginas: {max_pages}")
        print(f"   ⏱️  Tempo estimado: {max_pages * 0.5:.1f} minutos")
        
        # Executa comparação
        comparator = BulkVisualComparator(prod_domain, hml_domain, max_pages)
        comparator.run_comparison()
        
    except KeyboardInterrupt:
        print("\n⏹️ Processo interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro geral: {e}")
        
    print("\n" + "=" * 60)