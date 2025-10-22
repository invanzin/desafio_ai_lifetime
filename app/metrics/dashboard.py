import requests
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import time
import os
import sys
import math
from dataclasses import dataclass
from collections import defaultdict, deque
import statistics

@dataclass
class MetricSnapshot:
    """Snapshot de métricas em um momento específico"""
    timestamp: datetime
    openai_requests: int
    openai_errors: int
    total_cost: float
    avg_duration: float
    total_meetings: int
    success_rate: float

@dataclass
class Alert:
    """Estrutura para alertas do sistema"""
    severity: str  # 'INFO', 'WARN', 'CRIT'
    category: str  # 'PERFORMANCE', 'COST', 'ERROR', 'EFFICIENCY'
    message: str
    recommendation: str
    value: float
    threshold: float

@dataclass
class TrendData:
    """Dados de tendência para análise temporal"""
    metric_name: str
    current_value: float
    previous_value: float
    change_percent: float
    trend_direction: str  # 'UP', 'DOWN', 'STABLE'

class MetricsDashboard:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_url = f"{base_url}/metrics"
        self.history: deque = deque(maxlen=100)  # Histórico de snapshots
        self.alerts_history: List[Alert] = []
        self.previous_metrics: Optional[Dict] = None
        
        # Configurações de alertas
        self.alert_thresholds = {
            'error_rate': 15.0,  # %
            'avg_duration': 20.0,  # segundos
            'cost_per_meeting': 0.10,  # USD
            'success_rate': 85.0,  # %
            'token_efficiency': 0.1,  # completion/prompt ratio
        }
    
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
    
    def calculate_trends(self, current_metrics: Dict, previous_metrics: Dict) -> List[TrendData]:
        """Calcula tendências comparando métricas atuais com anteriores"""
        trends = []
        
        if not previous_metrics:
            return trends
        
        # Métricas para análise de tendência
        trend_metrics = [
            ('total_requests', current_metrics.get('requests', {}).get('success', 0) + current_metrics.get('requests', {}).get('error', 0)),
            ('total_cost', current_metrics.get('cost', 0)),
            ('avg_duration', current_metrics.get('avg_duration', 0)),
            ('success_rate', current_metrics.get('success_rate', 0)),
        ]
        
        for metric_name, current_value in trend_metrics:
            if metric_name == 'total_requests':
                prev_value = previous_metrics.get('requests', {}).get('success', 0) + previous_metrics.get('requests', {}).get('error', 0)
            elif metric_name == 'total_cost':
                prev_value = previous_metrics.get('cost', 0)
            elif metric_name == 'avg_duration':
                prev_value = previous_metrics.get('avg_duration', 0)
            elif metric_name == 'success_rate':
                prev_value = previous_metrics.get('success_rate', 0)
            else:
                prev_value = 0
            
            if prev_value > 0:
                change_percent = ((current_value - prev_value) / prev_value) * 100
            else:
                change_percent = 0 if current_value == 0 else 100
            
            if abs(change_percent) < 5:
                trend_direction = 'STABLE'
            elif change_percent > 0:
                trend_direction = 'UP'
            else:
                trend_direction = 'DOWN'
            
            trends.append(TrendData(
                metric_name=metric_name,
                current_value=current_value,
                previous_value=prev_value,
                change_percent=change_percent,
                trend_direction=trend_direction
            ))
        
        return trends
    
    def generate_advanced_alerts(self, metrics: Dict) -> List[Alert]:
        """Gera alertas avançados baseados em múltiplas métricas"""
        alerts = []
        
        # Análise de taxa de erro
        total_requests = metrics.get('requests', {}).get('success', 0) + metrics.get('requests', {}).get('error', 0)
        if total_requests > 0:
            error_rate = (metrics.get('requests', {}).get('error', 0) / total_requests) * 100
            if error_rate > self.alert_thresholds['error_rate']:
                severity = 'CRIT' if error_rate > 30 else 'WARN'
                alerts.append(Alert(
                    severity=severity,
                    category='ERROR',
                    message=f"Taxa de erro alta: {error_rate:.1f}%",
                    recommendation="Verificar conectividade com OpenAI API e logs de erro",
                    value=error_rate,
                    threshold=self.alert_thresholds['error_rate']
                ))
        
        # Análise de performance
        avg_duration = metrics.get('avg_duration', 0)
        if avg_duration > self.alert_thresholds['avg_duration']:
            severity = 'CRIT' if avg_duration > 60 else 'WARN'
            alerts.append(Alert(
                severity=severity,
                category='PERFORMANCE',
                message=f"Tempo médio de processamento alto: {self.format_duration(avg_duration)}",
                recommendation="Otimizar prompts ou considerar modelo mais rápido",
                value=avg_duration,
                threshold=self.alert_thresholds['avg_duration']
            ))
        
        # Análise de custo
        total_meetings = metrics.get('total_meetings', 0)
        if total_meetings > 0:
            cost_per_meeting = metrics.get('cost', 0) / total_meetings
            if cost_per_meeting > self.alert_thresholds['cost_per_meeting']:
                alerts.append(Alert(
                    severity='WARN',
                    category='COST',
                    message=f"Custo por reunião alto: ${cost_per_meeting:.4f}",
                    recommendation="Revisar tamanho das transcrições e otimizar prompts",
                    value=cost_per_meeting,
                    threshold=self.alert_thresholds['cost_per_meeting']
                ))
        
        # Análise de eficiência de tokens
        tokens = metrics.get('tokens', {})
        if tokens.get('prompt', 0) > 0 and tokens.get('completion', 0) > 0:
            efficiency = tokens.get('completion', 0) / tokens.get('prompt', 0)
            if efficiency < self.alert_thresholds['token_efficiency']:
                alerts.append(Alert(
                    severity='INFO',
                    category='EFFICIENCY',
                    message=f"Baixa eficiência de tokens: {efficiency:.2f}",
                    recommendation="Prompt muito longo ou resposta muito curta",
                    value=efficiency,
                    threshold=self.alert_thresholds['token_efficiency']
                ))
        
        return alerts
    
    def create_ascii_chart(self, data: Dict[str, float], title: str, max_width: int = 50) -> str:
        """Cria gráfico ASCII simples"""
        if not data:
            return f"{title}\n  Nenhum dado disponível"
        
        max_value = max(data.values()) if data.values() else 1
        chart_lines = [f"{title}"]
        chart_lines.append("-" * (max_width + 20))
        
        for key, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
            # Trunca chave se muito longa
            display_key = key[:25] + "..." if len(key) > 25 else key
            # Calcula largura da barra
            bar_width = int((value / max_value) * max_width) if max_value > 0 else 0
            bar = "█" * bar_width
            chart_lines.append(f"  {display_key:<28} {value:6.0f} {bar}")
        
        return "\n".join(chart_lines)
    
    def create_performance_gauge(self, value: float, max_value: float, label: str) -> str:
        """Cria medidor visual ASCII"""
        if max_value == 0:
            percentage = 0
        else:
            percentage = min(100, (value / max_value) * 100)
        
        # Cria barra de progresso
        bar_length = 20
        filled_length = int((percentage / 100) * bar_length)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        # Determina cor baseada na performance
        if percentage >= 80:
            status = "[EXCELLENT]"
        elif percentage >= 60:
            status = "[GOOD]"
        elif percentage >= 40:
            status = "[WARNING]"
        else:
            status = "[CRITICAL]"
        
        return f"{label}: {status}\n  [{bar}] {percentage:5.1f}% ({value:.2f}/{max_value:.2f})"
    
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
        
        # Custos - calcula baseado nos tokens reais
        prompt_tokens = tokens_data.get('prompt', 0)
        completion_tokens = tokens_data.get('completion', 0)
        
        # Preços corretos baseados no LangSmith
        prompt_cost_per_1k = 0.00132  # $0.00132 per 1K input tokens
        completion_cost_per_1k = 0.010  # $0.010 per 1K output tokens
        
        # Calcula custo real baseado nos tokens
        calculated_cost = ((prompt_tokens / 1000) * prompt_cost_per_1k) + ((completion_tokens / 1000) * completion_cost_per_1k)
        
        # Usa o custo calculado se disponível, senão usa o da métrica
        cost = calculated_cost if calculated_cost > 0 else sum(self.parse_metric(metrics_text, 'openai_estimated_cost_usd_total'))
        
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
    
    def calculate_statistics(self, metrics: Dict) -> Dict:
        """Calcula estatísticas avançadas"""
        stats = {}
        
        # Estatísticas de performance
        durations = [metrics.get('avg_duration', 0)]
        if durations[0] > 0:
            stats['performance'] = {
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'std_dev': statistics.stdev(durations) if len(durations) > 1 else 0,
                'min': min(durations),
                'max': max(durations)
            }
        
        # Estatísticas de custo
        costs = [metrics.get('cost', 0)]
        if costs[0] > 0:
            stats['cost'] = {
                'mean': statistics.mean(costs),
                'median': statistics.median(costs),
                'std_dev': statistics.stdev(costs) if len(costs) > 1 else 0,
                'min': min(costs),
                'max': max(costs)
            }
        
        return stats
    
    def create_heatmap_data(self, metrics: Dict) -> Dict:
        """Cria dados para visualização tipo heatmap"""
        heatmap = {}
        
        # Performance vs Custo
        performance_score = min(100, max(0, 100 - (metrics.get('avg_duration', 0) * 2)))
        cost_score = min(100, max(0, 100 - (metrics.get('cost', 0) * 1000)))
        efficiency_score = (performance_score + cost_score) / 2
        
        heatmap['performance'] = performance_score
        heatmap['cost_efficiency'] = cost_score
        heatmap['overall_efficiency'] = efficiency_score
        
        # Taxa de sucesso
        total_requests = metrics.get('requests', {}).get('success', 0) + metrics.get('requests', {}).get('error', 0)
        if total_requests > 0:
            success_rate = (metrics.get('requests', {}).get('success', 0) / total_requests) * 100
            heatmap['reliability'] = success_rate
        else:
            heatmap['reliability'] = 0
        
        return heatmap
    
    def print_advanced_header(self):
        """Imprime cabeçalho avançado do dashboard"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "="*100)
        print("🚀 [ADVANCED DASHBOARD] MICROSERVICO DE EXTRACAO DE REUNIOES")
        print(f"⏰ [TEMPO] Atualizado em: {now}")
        print(f"🌐 [API] {self.base_url}")
        print("="*100)
    
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
            
            # Custos reais por tipo (GPT-4o) - baseado no LangSmith
            prompt_cost_per_1k = 0.00132  # $0.00132 per 1K input tokens (baseado em 1624 tokens = $0.00214)
            completion_cost_per_1k = 0.010  # $0.010 per 1K output tokens (baseado em 500 tokens = $0.005)
            
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
    
    def print_advanced_visualizations(self, openai_metrics: Dict, performance_metrics: Dict, business_metrics: Dict):
        """Imprime visualizações avançadas"""
        print(f"\n🎨 [VISUALIZACOES AVANCADAS]")
        print("-" * 80)
        
        # Gráfico de distribuição de tipos de reunião
        if business_metrics['meetings_by_type']:
            print("\n📊 Distribuição de Tipos de Reunião:")
            print(self.create_ascii_chart(business_metrics['meetings_by_type'], "Tipos de Reunião", 40))
        
        # Medidores de performance
        print(f"\n⚡ Medidores de Performance:")
        
        # Performance de tempo
        avg_duration = performance_metrics['extraction']['avg_duration']
        print(self.create_performance_gauge(avg_duration, 30, "Tempo Médio de Processamento"))
        
        # Taxa de sucesso
        total_requests = openai_metrics['requests']['success'] + openai_metrics['requests']['error']
        if total_requests > 0:
            success_rate = (openai_metrics['requests']['success'] / total_requests) * 100
            print(f"\n{self.create_performance_gauge(success_rate, 100, 'Taxa de Sucesso')}")
        
        # Eficiência de custo
        if business_metrics['total_meetings'] > 0:
            cost_per_meeting = openai_metrics['cost'] / business_metrics['total_meetings']
            print(f"\n{self.create_performance_gauge(cost_per_meeting, 0.10, 'Custo por Reunião (USD)')}")
    
    def print_trend_analysis(self, trends: List[TrendData]):
        """Imprime análise de tendências"""
        if not trends:
            return
        
        print(f"\n📈 [ANALISE DE TENDENCIAS]")
        print("-" * 60)
        
        for trend in trends:
            direction_icon = "📈" if trend.trend_direction == "UP" else "📉" if trend.trend_direction == "DOWN" else "➡️"
            
            # Determina se a tendência é boa ou ruim
            is_good_trend = False
            if trend.metric_name == 'success_rate' and trend.trend_direction == "UP":
                is_good_trend = True
            elif trend.metric_name == 'avg_duration' and trend.trend_direction == "DOWN":
                is_good_trend = True
            elif trend.metric_name == 'total_cost' and trend.trend_direction == "DOWN":
                is_good_trend = True
            
            status = "✅" if is_good_trend else "⚠️" if trend.trend_direction != "STABLE" else "➡️"
            
            print(f"{status} {direction_icon} {trend.metric_name.replace('_', ' ').title()}: "
                  f"{trend.change_percent:+.1f}% "
                  f"({trend.previous_value:.2f} → {trend.current_value:.2f})")
    
    def print_heatmap_analysis(self, metrics: Dict):
        """Imprime análise tipo heatmap"""
        heatmap = self.create_heatmap_data(metrics)
        
        print(f"\n🔥 [HEATMAP DE EFICIENCIA]")
        print("-" * 60)
        
        # Performance Score
        perf_score = heatmap['performance']
        perf_bar = "█" * int(perf_score / 5) + "░" * (20 - int(perf_score / 5))
        perf_status = "EXCELLENT" if perf_score >= 80 else "GOOD" if perf_score >= 60 else "WARNING" if perf_score >= 40 else "CRITICAL"
        print(f"🚀 Performance:    [{perf_bar}] {perf_score:5.1f}% [{perf_status}]")
        
        # Reliability Score
        rel_score = heatmap['reliability']
        rel_bar = "█" * int(rel_score / 5) + "░" * (20 - int(rel_score / 5))
        rel_status = "EXCELLENT" if rel_score >= 95 else "GOOD" if rel_score >= 85 else "WARNING" if rel_score >= 70 else "CRITICAL"
        print(f"🛡️  Confiabilidade: [{rel_bar}] {rel_score:5.1f}% [{rel_status}]")
        
        # Cost Efficiency Score
        cost_score = heatmap['cost_efficiency']
        cost_bar = "█" * int(cost_score / 5) + "░" * (20 - int(cost_score / 5))
        cost_status = "EXCELLENT" if cost_score >= 80 else "GOOD" if cost_score >= 60 else "WARNING" if cost_score >= 40 else "CRITICAL"
        print(f"💰 Eficiência:     [{cost_bar}] {cost_score:5.1f}% [{cost_status}]")
        
        # Overall Score
        overall_score = heatmap['overall_efficiency']
        overall_bar = "█" * int(overall_score / 5) + "░" * (20 - int(overall_score / 5))
        overall_status = "EXCELLENT" if overall_score >= 80 else "GOOD" if overall_score >= 60 else "WARNING" if overall_score >= 40 else "CRITICAL"
        print(f"🎯 Score Geral:    [{overall_bar}] {overall_score:5.1f}% [{overall_status}]")
    
    def print_statistical_analysis(self, metrics: Dict):
        """Imprime análise estatística avançada"""
        stats = self.calculate_statistics(metrics)
        
        print(f"\n📊 [ANALISE ESTATISTICA]")
        print("-" * 60)
        
        if 'performance' in stats:
            perf = stats['performance']
            print(f"⏱️  Performance (Tempo):")
            print(f"   Média: {perf['mean']:.2f}s | Mediana: {perf['median']:.2f}s")
            print(f"   Desvio: {perf['std_dev']:.2f}s | Range: {perf['min']:.2f}s - {perf['max']:.2f}s")
        
        if 'cost' in stats:
            cost = stats['cost']
            print(f"\n💰 Custo:")
            print(f"   Média: ${cost['mean']:.4f} | Mediana: ${cost['median']:.4f}")
            print(f"   Desvio: ${cost['std_dev']:.4f} | Range: ${cost['min']:.4f} - ${cost['max']:.4f}")
        
        # Análise de eficiência
        tokens = metrics.get('tokens', {})
        if tokens.get('prompt', 0) > 0 and tokens.get('completion', 0) > 0:
            efficiency = tokens.get('completion', 0) / tokens.get('prompt', 0)
            print(f"\n🎯 Eficiência de Tokens: {efficiency:.2f}")
            
            if efficiency > 0.5:
                print("   ✅ Alta eficiência - boa proporção prompt/resposta")
            elif efficiency > 0.2:
                print("   ⚠️  Eficiência moderada - considere otimizar prompts")
            else:
                print("   ❌ Baixa eficiência - prompts muito longos ou respostas muito curtas")
    
    def print_advanced_alerts(self, alerts: List[Alert]):
        """Imprime alertas avançados com categorização"""
        if not alerts:
            print(f"\n✅ [SISTEMA SAUDAVEL] Nenhum alerta ativo")
            return
        
        print(f"\n🚨 [ALERTAS AVANCADOS]")
        print("-" * 80)
        
        # Agrupa alertas por categoria
        by_category = defaultdict(list)
        for alert in alerts:
            by_category[alert.category].append(alert)
        
        # Ícones por categoria
        category_icons = {
            'ERROR': '❌',
            'PERFORMANCE': '⚡',
            'COST': '💰',
            'EFFICIENCY': '🎯'
        }
        
        for category, category_alerts in by_category.items():
            icon = category_icons.get(category, '⚠️')
            print(f"\n{icon} {category}:")
            
            for alert in category_alerts:
                severity_icon = "🔴" if alert.severity == "CRIT" else "🟡" if alert.severity == "WARN" else "🔵"
                print(f"   {severity_icon} {alert.message}")
                print(f"      💡 {alert.recommendation}")
                print(f"      📊 Valor: {alert.value:.2f} | Limite: {alert.threshold:.2f}")
    
    def generate_advanced_dashboard(self):
        """Gera o dashboard avançado completo"""
        metrics_text = self.get_metrics()
        if not metrics_text:
            self.print_advanced_header()
            print("\n❌ [ERROR] Nao foi possivel obter metricas")
            print("🔧 [SOLUTION] Para iniciar a API:")
            print("  1. cd projeto")
            print("  2. venv\\Scripts\\activate  (Windows)")
            print("  3. uvicorn app.main:app --reload")
            return
        
        # Extrair métricas
        openai_metrics = self.get_openai_metrics(metrics_text)
        performance_metrics = self.get_performance_metrics(metrics_text)
        business_metrics = self.get_business_metrics(metrics_text)
        
        # Combinar métricas para análise
        combined_metrics = {
            'requests': openai_metrics['requests'],
            'cost': openai_metrics['cost'],
            'tokens': openai_metrics['tokens'],
            'avg_duration': performance_metrics['extraction']['avg_duration'],
            'total_meetings': business_metrics['total_meetings'],
            'success_rate': (openai_metrics['requests']['success'] / 
                           (openai_metrics['requests']['success'] + openai_metrics['requests']['error']) * 100 
                           if (openai_metrics['requests']['success'] + openai_metrics['requests']['error']) > 0 else 0)
        }
        
        # Calcular tendências
        trends = self.calculate_trends(combined_metrics, self.previous_metrics)
        
        # Gerar alertas avançados
        alerts = self.generate_advanced_alerts(combined_metrics)
        
        # Salvar métricas para próxima comparação
        self.previous_metrics = combined_metrics.copy()
        
        # Imprimir dashboard avançado
        self.print_advanced_header()
        self.print_health_section(openai_metrics, performance_metrics)
        self.print_business_section(business_metrics)
        self.print_openai_section(openai_metrics)
        self.print_performance_section(performance_metrics)
        
        # Seções avançadas
        self.print_advanced_visualizations(openai_metrics, performance_metrics, business_metrics)
        self.print_trend_analysis(trends)
        self.print_heatmap_analysis(combined_metrics)
        self.print_statistical_analysis(combined_metrics)
        self.print_advanced_alerts(alerts)
        
        # Análise de custos e resumo
        self.print_cost_analysis(openai_metrics, performance_metrics, business_metrics)
        self.print_summary(openai_metrics, performance_metrics, business_metrics)
        
        print("\n" + "="*100)
        print("💡 [TIPS] Comandos disponíveis:")
        print("   python dashboard.py --watch    (monitoramento em tempo real)")
        print("   python dashboard.py --advanced (dashboard avançado)")
        print("   python dashboard.py --simple   (dashboard simples)")
        print("="*100 + "\n")
    
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
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "--watch":
            # Modo watch - atualiza a cada 10 segundos
            print("🔄 [WATCH] Modo monitoramento ativo (Ctrl+C para sair)")
            try:
                while True:
                    os.system('cls' if os.name == 'nt' else 'clear')  # Limpa tela
                    dashboard.generate_advanced_dashboard()
                    time.sleep(10)
            except KeyboardInterrupt:
                print("\n🚪 [EXIT] Monitoramento interrompido!")
        
        elif mode == "--advanced":
            # Modo dashboard avançado
            dashboard.generate_advanced_dashboard()
        
        elif mode == "--simple":
            # Modo dashboard simples
            dashboard.generate_dashboard()
        
        elif mode == "--help":
            print("🚀 [DASHBOARD] MICROSERVICO DE EXTRACAO DE REUNIOES")
            print("="*60)
            print("📋 Comandos disponíveis:")
            print("   python dashboard.py              (dashboard padrão)")
            print("   python dashboard.py --simple     (dashboard simples)")
            print("   python dashboard.py --advanced   (dashboard avançado)")
            print("   python dashboard.py --watch      (monitoramento em tempo real)")
            print("   python dashboard.py --help       (esta ajuda)")
            print("\n💡 O dashboard avançado inclui:")
            print("   • Gráficos ASCII e visualizações")
            print("   • Análise de tendências")
            print("   • Heatmap de eficiência")
            print("   • Análise estatística")
            print("   • Alertas inteligentes")
            print("   • Medidores de performance")
            print("="*60)
        
        else:
            print(f"❌ [ERROR] Modo desconhecido: {mode}")
            print("💡 Use --help para ver os comandos disponíveis")
    
    else:
        # Modo padrão - dashboard avançado
        dashboard.generate_advanced_dashboard()

if __name__ == "__main__":
    main()
