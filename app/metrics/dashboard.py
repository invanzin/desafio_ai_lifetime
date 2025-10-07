import requests
import re
import json
from datetime import datetime
from typing import Dict, List, Tuple
import time
import os
import sys

class MetricsDashboard:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_url = f"{base_url}/metrics"
    
    def get_metrics(self) -> str:
        """Obtém métricas brutas do endpoint /metrics"""
        try:
            response = requests.get(self.metrics_url, timeout=5)
            response.raise_for_status()
    return response.text
        except requests.ConnectionError:
            print(f"[ERROR] API nao esta rodando em {self.base_url}")
            print(f"[TIP] Inicie a API com: uvicorn app.main:app --reload")
            return ""
        except requests.RequestException as e:
            print(f"[ERROR] Erro ao conectar com a API: {e}")
            return ""
    
    def parse_metric(self, metrics_text: str, metric_name: str) -> List[float]:
        """Extrai valores de uma métrica específica"""
    pattern = f'{metric_name}{{[^}}]*}} ([0-9.]+)'
    matches = re.findall(pattern, metrics_text)
    return [float(m) for m in matches]

    def parse_labeled_metric(self, metrics_text: str, metric_name: str) -> Dict[str, float]:
        """Extrai métricas com labels (ex: por tipo de reunião)"""
        pattern = f'{metric_name}{{([^}}]+)}} ([0-9.]+)'
        matches = re.findall(pattern, metrics_text)
        result = {}
        for labels, value in matches:
            # Extrai o valor do label principal (ex: meeting_type="Onboarding")
            label_match = re.search(r'[^=]+="([^"]+)"', labels)
            if label_match:
                key = label_match.group(1)
                result[key] = float(value)
        return result
    
    def get_openai_metrics(self, metrics_text: str) -> Dict:
        """Extrai todas as métricas relacionadas à OpenAI"""
        # Parse das requisições com labels
        requests_data = self.parse_labeled_metric(metrics_text, 'openai_requests_total')
        success = requests_data.get('success', 0)
        error = requests_data.get('error', 0)
        
        # Tokens por tipo
        tokens_data = self.parse_labeled_metric(metrics_text, 'openai_tokens_total')
        prompt_tokens = tokens_data.get('prompt', 0)
        completion_tokens = tokens_data.get('completion', 0)
        total_tokens = tokens_data.get('total', 0)
        
        # Custos
        cost = sum(self.parse_metric(metrics_text, 'openai_estimated_cost_usd_total'))
        
        # Reparos
        repairs_data = self.parse_labeled_metric(metrics_text, 'openai_repair_attempts_total')
        repairs_success = repairs_data.get('success', 0)
        repairs_failed = repairs_data.get('failed', 0)
        
        # Tipos de erro
        errors_by_type = self.parse_labeled_metric(metrics_text, 'openai_errors_total')
        
        return {
            'requests': {'success': success, 'error': error},
            'tokens': {
                'prompt': prompt_tokens,
                'completion': completion_tokens, 
                'total': total_tokens
            },
            'cost': cost,
            'repairs': {'success': repairs_success, 'failed': repairs_failed},
            'errors_by_type': errors_by_type
        }
    
    def get_performance_metrics(self, metrics_text: str) -> Dict:
        """Extrai métricas de performance"""
        # Duração da extração
        extraction_sum = sum(self.parse_metric(metrics_text, 'extraction_duration_seconds_sum'))
        extraction_count = sum(self.parse_metric(metrics_text, 'extraction_duration_seconds_count'))
        
        # Duração HTTP
        http_sum = sum(self.parse_metric(metrics_text, 'http_requests_duration_seconds_sum'))
        http_count = sum(self.parse_metric(metrics_text, 'http_requests_duration_seconds_count'))
        
        # Tamanho das transcrições
        transcript_sum = sum(self.parse_metric(metrics_text, 'transcript_size_bytes_sum'))
        transcript_count = sum(self.parse_metric(metrics_text, 'transcript_size_bytes_count'))
        
        return {
            'extraction': {
                'avg_duration': extraction_sum / extraction_count if extraction_count > 0 else 0,
                'total_time': extraction_sum,
                'count': extraction_count
            },
            'http': {
                'avg_duration': http_sum / http_count if http_count > 0 else 0,
                'total_time': http_sum,
                'count': http_count
            },
            'transcripts': {
                'avg_size': transcript_sum / transcript_count if transcript_count > 0 else 0,
                'total_size': transcript_sum,
                'count': transcript_count
            }
        }
    
    def get_business_metrics(self, metrics_text: str) -> Dict:
        """Extrai métricas de negócio"""
        # Reuniões por fonte
        meetings_by_source = self.parse_labeled_metric(metrics_text, 'meetings_extracted_total')
        
        # Reuniões por tipo
        meetings_by_type = self.parse_labeled_metric(metrics_text, 'meetings_by_type_total')
        
        # Rate limiting
        rate_limits = sum(self.parse_metric(metrics_text, 'rate_limit_exceeded_total'))
        
        return {
            'meetings_by_source': meetings_by_source,
            'meetings_by_type': meetings_by_type,
            'rate_limits': rate_limits,
            'total_meetings': sum(meetings_by_source.values())
        }
    
    def format_bytes(self, bytes_value: float) -> str:
        """Formata bytes em unidades legíveis"""
        if bytes_value < 1024:
            return f"{bytes_value:.0f} B"
        elif bytes_value < 1024**2:
            return f"{bytes_value/1024:.1f} KB"
        else:
            return f"{bytes_value/(1024**2):.1f} MB"
    
    def format_duration(self, seconds: float) -> str:
        """Formata duração em formato legível"""
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            return f"{seconds/60:.1f}min"
    
    def get_health_status(self, openai_metrics: Dict, performance_metrics: Dict) -> Tuple[str, str]:
        """Determina o status de saúde do sistema"""
        success_rate = 0
        if openai_metrics['requests']['success'] + openai_metrics['requests']['error'] > 0:
            success_rate = (openai_metrics['requests']['success'] / 
                          (openai_metrics['requests']['success'] + openai_metrics['requests']['error'])) * 100
        
        avg_duration = performance_metrics['extraction']['avg_duration']
        
        # Critérios de saúde
        if success_rate >= 95 and avg_duration <= 10:
            return "[OK] EXCELENTE", "green"
        elif success_rate >= 85 and avg_duration <= 20:
            return "[GOOD] BOM", "yellow"
        elif success_rate >= 70 and avg_duration <= 30:
            return "[WARN] ATENCAO", "orange"
        else:
            return "[CRIT] CRITICO", "red"
    
    def print_header(self):
        """Imprime cabeçalho do dashboard"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "="*80)
        print("[DASHBOARD] MICROSERVICO DE EXTRACAO DE REUNIOES")
        print(f"[TEMPO] Atualizado em: {now}")
        print("="*80)
    
    def print_health_section(self, openai_metrics: Dict, performance_metrics: Dict):
        """Imprime seção de saúde do sistema"""
        status, color = self.get_health_status(openai_metrics, performance_metrics)
        
        print(f"\n[HEALTH] STATUS DO SISTEMA")
        print("-" * 50)
        print(f"Status Geral: {status}")
        
        # Taxa de sucesso
        total_requests = openai_metrics['requests']['success'] + openai_metrics['requests']['error']
        if total_requests > 0:
            success_rate = (openai_metrics['requests']['success'] / total_requests) * 100
            print(f"Taxa de Sucesso: {success_rate:.1f}% ({openai_metrics['requests']['success']}/{total_requests})")
        else:
            print("Taxa de Sucesso: N/A (sem requisicoes)")
        
        # Performance
        avg_duration = performance_metrics['extraction']['avg_duration']
        print(f"Tempo Medio: {self.format_duration(avg_duration)}")
    
    def print_business_section(self, business_metrics: Dict):
        """Imprime seção de métricas de negócio"""
        print(f"\n[BUSINESS] METRICAS DE NEGOCIO")
        print("-" * 50)
        print(f"Total de Reunioes: {business_metrics['total_meetings']:.0f}")
        
        if business_metrics['meetings_by_source']:
            print("\nPor Fonte de Dados:")
            for source, count in business_metrics['meetings_by_source'].items():
                percentage = (count / business_metrics['total_meetings']) * 100 if business_metrics['total_meetings'] > 0 else 0
                bar = "#" * int(percentage / 5)  # Barra visual
                print(f"  > {source:15} {count:3.0f} ({percentage:5.1f}%) {bar}")
        
        if business_metrics['meetings_by_type']:
            print("\nPor Tipo de Reuniao:")
            for meeting_type, count in business_metrics['meetings_by_type'].items():
                percentage = (count / business_metrics['total_meetings']) * 100 if business_metrics['total_meetings'] > 0 else 0
                # Trunca nome longo
                short_name = meeting_type[:25] + "..." if len(meeting_type) > 25 else meeting_type
                bar = "#" * int(percentage / 5)
                print(f"  > {short_name:28} {count:3.0f} ({percentage:5.1f}%) {bar}")
        
        if business_metrics['rate_limits'] > 0:
            print(f"\n[WARN] Rate Limits Atingidos: {business_metrics['rate_limits']:.0f}")
    
    def print_openai_section(self, openai_metrics: Dict):
        """Imprime seção de métricas da OpenAI"""
        print(f"\n[OPENAI] API METRICS")
        print("-" * 50)
        
        # Requisições
        total_requests = openai_metrics['requests']['success'] + openai_metrics['requests']['error']
        print(f"Requisicoes Totais: {total_requests:.0f}")
        print(f"  > Sucessos: {openai_metrics['requests']['success']:8.0f}")
        print(f"  > Erros:    {openai_metrics['requests']['error']:8.0f}")
        
        # Médias de tokens por requisição
        if total_requests > 0 and openai_metrics['tokens']['total'] > 0:
            avg_prompt_per_req = openai_metrics['tokens']['prompt'] / total_requests
            avg_completion_per_req = openai_metrics['tokens']['completion'] / total_requests
            avg_total_per_req = openai_metrics['tokens']['total'] / total_requests
            
            print(f"\nTokens por Requisicao:")
            print(f"  > Prompt medio:    {avg_prompt_per_req:8.0f} tokens/req")
            print(f"  > Completion medio: {avg_completion_per_req:8.0f} tokens/req")
            print(f"  > Total medio:     {avg_total_per_req:8.0f} tokens/req")
        
        # Tokens com visualização
        if openai_metrics['tokens']['total'] > 0:
            print(f"\nTokens Processados:")
            print(f"  > Prompt:     {openai_metrics['tokens']['prompt']:10.0f}")
            print(f"  > Completion: {openai_metrics['tokens']['completion']:10.0f}")
            print(f"  > Total:      {openai_metrics['tokens']['total']:10.0f}")
            
            # Análise detalhada de custos
            if openai_metrics['cost'] > 0:
                cost_str = f"${openai_metrics['cost']:.4f}"
                if openai_metrics['cost'] > 0.1:
                    cost_str += " [HIGH COST!]"
                elif openai_metrics['cost'] > 0.05:
                    cost_str += " [MEDIUM COST]"
                print(f"  > Custo Total: {cost_str}")
                
                # Análise por tipo de token
                if openai_metrics['tokens']['total'] > 0:
                    total_tokens = openai_metrics['tokens']['total']
                    prompt_tokens = openai_metrics['tokens']['prompt']
                    completion_tokens = openai_metrics['tokens']['completion']
                    
                    # Custo por token (aproximado para GPT-4o)
                    cost_per_1k_tokens = openai_metrics['cost'] / (total_tokens / 1000)
                    print(f"  > Custo/1K tokens: ${cost_per_1k_tokens:.4f}")
                    
                    # Distribuição de custos
                    prompt_cost_ratio = (prompt_tokens / total_tokens) * 100
                    completion_cost_ratio = (completion_tokens / total_tokens) * 100
                    print(f"  > Prompt: {prompt_cost_ratio:.1f}% | Completion: {completion_cost_ratio:.1f}%")
                    
                    # Eficiência de tokens
                    if total_requests > 0:
                        avg_tokens_per_req = total_tokens / total_requests
                        cost_per_req = openai_metrics['cost'] / total_requests
                        print(f"  > Por requisicao: ${cost_per_req:.4f} ({avg_tokens_per_req:.0f} tokens)")
                        
                        # Eficiência por tipo de token
                        if prompt_tokens > 0:
                            prompt_efficiency = completion_tokens / prompt_tokens
                            print(f"  > Eficiencia: {prompt_efficiency:.2f} (completion/prompt)")
                else:
                    # Projeção de custo simples
                    if total_requests > 0:
                        cost_per_req = openai_metrics['cost'] / total_requests
                        print(f"  > Por requisicao: ${cost_per_req:.4f}")
        
        # Reparos de JSON
        total_repairs = openai_metrics['repairs']['success'] + openai_metrics['repairs']['failed']
        if total_repairs > 0:
            repair_rate = (openai_metrics['repairs']['success'] / total_repairs) * 100
            print(f"\nReparos de JSON: {total_repairs:.0f} (sucesso: {repair_rate:.1f}%)")
        else:
            print(f"\n[GOOD] Nenhum reparo de JSON necessario!")
        
        # Erros por tipo
        if openai_metrics['errors_by_type']:
            print(f"\nErros por Tipo:")
            for error_type, count in openai_metrics['errors_by_type'].items():
                print(f"  > {error_type}: {count:.0f}")
    
    def print_performance_section(self, performance_metrics: Dict):
        """Imprime seção de performance"""
        print(f"\n[PERFORMANCE] METRICAS DE VELOCIDADE")
        print("-" * 50)
        
        # Extração
        ext = performance_metrics['extraction']
        if ext['count'] > 0:
            print(f"Extracao (OpenAI):")
            avg_str = self.format_duration(ext['avg_duration'])
            if ext['avg_duration'] > 20:
                avg_str += " [SLOW!]"
            elif ext['avg_duration'] < 5:
                avg_str += " [FAST!]"
            print(f"  > Tempo Medio: {avg_str}")
            print(f"  > Tempo Total: {self.format_duration(ext['total_time'])}")
            print(f"  > Chamadas:    {ext['count']:.0f}")
        
        # HTTP
        http = performance_metrics['http']
        if http['count'] > 0:
            print(f"\nRequisicoes HTTP:")
            print(f"  > Tempo Medio: {self.format_duration(http['avg_duration'])}")
            print(f"  > Tempo Total: {self.format_duration(http['total_time'])}")
            print(f"  > Requisicoes: {http['count']:.0f}")
        
        # Transcrições com análise de tamanho
        trans = performance_metrics['transcripts']
        if trans['count'] > 0:
            print(f"\nTranscricoes:")
            avg_size_str = self.format_bytes(trans['avg_size'])
            if trans['avg_size'] > 50000:  # > 50KB
                avg_size_str += " [LARGE!]"
            elif trans['avg_size'] < 1000:  # < 1KB
                avg_size_str += " [SMALL]"
            print(f"  > Tamanho Medio: {avg_size_str}")
            print(f"  > Tamanho Total: {self.format_bytes(trans['total_size'])}")
            print(f"  > Processadas:   {trans['count']:.0f}")
    
    def print_alerts(self, openai_metrics: Dict, performance_metrics: Dict, business_metrics: Dict):
        """Imprime alertas baseados nas métricas"""
        alerts = []
        recommendations = []
        
        # Verificar taxa de erro alta
        total_requests = openai_metrics['requests']['success'] + openai_metrics['requests']['error']
        if total_requests > 0:
            error_rate = (openai_metrics['requests']['error'] / total_requests) * 100
            if error_rate > 20:
                alerts.append(f"[ALERT] Taxa de erro alta: {error_rate:.1f}%")
                recommendations.append("Verificar conectividade com OpenAI API")
        
        # Verificar tempo de resposta alto
        avg_duration = performance_metrics['extraction']['avg_duration']
        if avg_duration > 30:
            alerts.append(f"[SLOW] Tempo de extracao alto: {self.format_duration(avg_duration)}")
            recommendations.append("Considerar otimizar prompts ou usar modelo mais rapido")
        
        # Verificar custo alto
        if openai_metrics['cost'] > 1.0:
            alerts.append(f"[COST] Custo alto: ${openai_metrics['cost']:.2f}")
            recommendations.append("Monitorar custos - considerar limites de tokens")
        
        # Verificar rate limits
        if business_metrics['rate_limits'] > 0:
            alerts.append(f"[RATE] Rate limits atingidos: {business_metrics['rate_limits']:.0f}")
            recommendations.append("Implementar backoff ou aumentar limites")
        
        # Verificar eficiência de tokens
        if openai_metrics['tokens']['total'] > 0:
            avg_tokens = openai_metrics['tokens']['total'] / total_requests if total_requests > 0 else 0
            if avg_tokens > 15000:
                alerts.append(f"[TOKENS] Uso alto de tokens: {avg_tokens:.0f} por req")
                recommendations.append("Otimizar tamanho das transcricoes ou prompts")
            
            # Verificar proporção prompt/completion
            prompt_tokens = openai_metrics['tokens']['prompt']
            completion_tokens = openai_metrics['tokens']['completion']
            if prompt_tokens > 0:
                ratio = completion_tokens / prompt_tokens
                if ratio < 0.1:
                    alerts.append(f"[EFFICIENCY] Baixa eficiencia: {ratio:.2f} completion/prompt")
                    recommendations.append("Prompt muito longo ou resposta muito curta")
                elif ratio > 2.0:
                    alerts.append(f"[EFFICIENCY] Alta eficiencia: {ratio:.2f} completion/prompt")
                    recommendations.append("Considerar prompt mais detalhado para respostas menores")
        
        # Verificar custo por token
        if openai_metrics['cost'] > 0 and openai_metrics['tokens']['total'] > 0:
            cost_per_1k = openai_metrics['cost'] / (openai_metrics['tokens']['total'] / 1000)
            if cost_per_1k > 0.03:  # GPT-4o padrão é ~$0.03/1K tokens
                alerts.append(f"[COST] Custo por token alto: ${cost_per_1k:.4f}/1K")
                recommendations.append("Verificar modelo sendo usado - considere GPT-3.5-turbo para tarefas simples")
        
        if alerts:
            print(f"\n[ALERTS] ALERTAS DO SISTEMA")
            print("-" * 50)
            for i, alert in enumerate(alerts, 1):
                print(f"  {i}. {alert}")
            
            if recommendations:
                print(f"\n[TIPS] RECOMENDACOES:")
                for i, rec in enumerate(recommendations, 1):
                    print(f"  {i}. {rec}")
        else:
            print(f"\n[OK] SISTEMA SAUDAVEL - Nenhum alerta ativo")
    
    def print_cost_analysis(self, openai_metrics: Dict, performance_metrics: Dict, business_metrics: Dict):
        """Imprime análise detalhada de custos"""
        print(f"\n[COST ANALYSIS] ANALISE DETALHADA DE CUSTOS")
        print("-" * 60)
        
        total_cost = openai_metrics['cost']
        total_tokens = openai_metrics['tokens']['total']
        total_meetings = business_metrics['total_meetings']
        
        if total_cost > 0 and total_tokens > 0:
            # Análise por tipo de token
            prompt_tokens = openai_metrics['tokens']['prompt']
            completion_tokens = openai_metrics['tokens']['completion']
            
            # Custos aproximados por tipo (GPT-4o)
            prompt_cost_per_1k = 0.005  # $0.005 per 1K input tokens
            completion_cost_per_1k = 0.015  # $0.015 per 1K output tokens
            
            estimated_prompt_cost = (prompt_tokens / 1000) * prompt_cost_per_1k
            estimated_completion_cost = (completion_tokens / 1000) * completion_cost_per_1k
            
            print(f"Breakdown de Custos (estimativa GPT-4o):")
            print(f"  > Input tokens:  {prompt_tokens:8.0f} (${estimated_prompt_cost:.4f})")
            print(f"  > Output tokens: {completion_tokens:8.0f} (${estimated_completion_cost:.4f})")
            print(f"  > Total estimado: ${estimated_prompt_cost + estimated_completion_cost:.4f}")
            print(f"  > Custo real:     ${total_cost:.4f}")
            
            # Diferença
            diff = total_cost - (estimated_prompt_cost + estimated_completion_cost)
            if abs(diff) > 0.001:
                print(f"  > Diferenca:      ${diff:.4f}")
            
            # Eficiência de custos
            if total_meetings > 0:
                cost_per_meeting = total_cost / total_meetings
                tokens_per_meeting = total_tokens / total_meetings
                
                print(f"\nEficiencia por Reuniao:")
                print(f"  > Custo medio: ${cost_per_meeting:.4f}")
                print(f"  > Tokens medio: {tokens_per_meeting:.0f}")
                print(f"  > Custo/token: ${total_cost / total_tokens:.6f}")
                
                # Classificação de eficiência
                if cost_per_meeting < 0.01:
                    efficiency = "[EXCELLENT] Muito eficiente"
                elif cost_per_meeting < 0.05:
                    efficiency = "[GOOD] Eficiente"
                elif cost_per_meeting < 0.10:
                    efficiency = "[MEDIUM] Moderado"
                else:
                    efficiency = "[HIGH] Custo alto"
                
                print(f"  > Classificacao: {efficiency}")
        else:
            print("Nenhum dado de custo disponivel")
    
    def print_summary(self, openai_metrics: Dict, performance_metrics: Dict, business_metrics: Dict):
        """Imprime resumo executivo"""
        print(f"\n[SUMMARY] RESUMO EXECUTIVO")
        print("-" * 50)
        
        total_requests = openai_metrics['requests']['success'] + openai_metrics['requests']['error']
        total_meetings = business_metrics['total_meetings']
        total_cost = openai_metrics['cost']
        
        if total_meetings > 0:
            avg_cost_per_meeting = total_cost / total_meetings
            print(f"Reunioes processadas: {total_meetings:.0f}")
            print(f"Custo total: ${total_cost:.4f}")
            print(f"Custo por reuniao: ${avg_cost_per_meeting:.4f}")
            
            if openai_metrics['tokens']['total'] > 0:
                avg_tokens = openai_metrics['tokens']['total'] / total_meetings
                print(f"Tokens por reuniao: {avg_tokens:.0f}")
            
            if performance_metrics['extraction']['count'] > 0:
                avg_time = performance_metrics['extraction']['avg_duration']
                print(f"Tempo medio: {self.format_duration(avg_time)}")
                
                # Análise de ROI
                if openai_metrics['tokens']['total'] > 0:
                    avg_tokens = openai_metrics['tokens']['total'] / total_meetings
                    print(f"Tokens medio: {avg_tokens:.0f}")
                    
                    # Custo por minuto de transcrição (estimativa)
                    if performance_metrics['transcripts']['avg_size'] > 0:
                        avg_chars = performance_metrics['transcripts']['avg_size']
                        estimated_minutes = avg_chars / 1000  # ~1000 chars/min de fala
                        cost_per_minute = avg_cost_per_meeting / estimated_minutes if estimated_minutes > 0 else 0
                        print(f"Custo/min transcricao: ${cost_per_minute:.4f}")
                
                # Projecoes detalhadas
                print(f"\n[PROJECTIONS] Para 100 reunioes:")
                print(f"  Custo estimado: ${avg_cost_per_meeting * 100:.2f}")
                print(f"  Tempo estimado: {self.format_duration(avg_time * 100)}")
                
                if openai_metrics['tokens']['total'] > 0:
                    projected_tokens = (openai_metrics['tokens']['total'] / total_meetings) * 100
                    print(f"  Tokens estimados: {projected_tokens:.0f}")
                    
                    # Projeção mensal
                    monthly_meetings = 100 * 30  # 100 por dia x 30 dias
                    monthly_cost = avg_cost_per_meeting * monthly_meetings
                    print(f"\n[MONTHLY] Projecao mensal (100 reunioes/dia):")
                    print(f"  Custo mensal: ${monthly_cost:.2f}")
                    print(f"  Custo anual: ${monthly_cost * 12:.2f}")
                    
                    # Comparação com alternativas
                    print(f"\n[COMPARISON] Alternativas:")
                    human_cost_per_meeting = 50.0  # $50 por reunião processada manualmente
                    savings_per_meeting = human_cost_per_meeting - avg_cost_per_meeting
                    print(f"  Custo humano estimado: ${human_cost_per_meeting:.2f}/reuniao")
                    print(f"  Economia por reuniao: ${savings_per_meeting:.2f}")
                    print(f"  Economia mensal: ${savings_per_meeting * monthly_meetings:.2f}")
        else:
            print("Nenhuma reuniao processada ainda")
            print("Execute algumas requisicoes para ver estatisticas")
    
    def generate_dashboard(self):
        """Gera o dashboard completo"""
        metrics_text = self.get_metrics()
        if not metrics_text:
            print("\n" + "="*80)
            print("[DASHBOARD] MICROSERVICO DE EXTRACAO DE REUNIOES")
            print(f"[TEMPO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)
            print("\n[ERROR] Nao foi possivel obter metricas")
            print("[STATUS] API provavelmente nao esta rodando")
            print("\n[SOLUTION] Para iniciar a API:")
            print("  1. cd projeto")
            print("  2. venv\\Scripts\\activate  (Windows)")
            print("  3. uvicorn app.main:app --reload")
            print("\n" + "="*80 + "\n")
            return
        
        # Extrair métricas
        openai_metrics = self.get_openai_metrics(metrics_text)
        performance_metrics = self.get_performance_metrics(metrics_text)
        business_metrics = self.get_business_metrics(metrics_text)
        
        # Imprimir dashboard
        self.print_header()
        self.print_health_section(openai_metrics, performance_metrics)
        self.print_business_section(business_metrics)
        self.print_openai_section(openai_metrics)
        self.print_performance_section(performance_metrics)
        self.print_alerts(openai_metrics, performance_metrics, business_metrics)
        
        # Análise de custos detalhada
        self.print_cost_analysis(openai_metrics, performance_metrics, business_metrics)
        
        # Resumo final
        self.print_summary(openai_metrics, performance_metrics, business_metrics)
        
        print("\n" + "="*80)
        print("[TIP] Execute 'python dashboard.py --watch' para monitoramento em tempo real")
        print("[TIP] Pressione Ctrl+C para sair do modo watch")
        print("="*80 + "\n")

def main():
    """Função principal"""
    dashboard = MetricsDashboard()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        # Modo watch - atualiza a cada 10 segundos
        print("[WATCH] Modo monitoramento ativo (Ctrl+C para sair)")
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')  # Limpa tela
                dashboard.generate_dashboard()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n[EXIT] Monitoramento interrompido!")
    else:
        # Modo single shot
        dashboard.generate_dashboard()

if __name__ == "__main__":
    main()
