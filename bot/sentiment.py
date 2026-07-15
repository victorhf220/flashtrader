import logging
import time
from typing import Dict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
import requests

from config import (
    TWITTER_BEARER,
    REDDIT_CLIENT,
    REDDIT_SECRET,
    TELEGRAM_ID,
    TELEGRAM_HASH,
    NEWSAPI_KEY,
    SENTIMENT_WEIGHTS,
    CACHE_SENTIMENTO_TTL,
    MERCADOS,
)

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.cache = {}
        self.cache_timestamp = {}
        
    def get_sentiment_score(self, text: str) -> float:
        """
        Retorna score de sentimento entre -1 (muito negativo) e +1 (muito positivo)
        usando VADER + TextBlob em ensemble
        """
        try:
            # VADER (otimizado para redes sociais)
            vader_scores = self.vader.polarity_scores(text)
            vader_compound = vader_scores['compound']  # -1 a +1
            
            # TextBlob (análise adicional)
            blob = TextBlob(text)
            textblob_polarity = blob.sentiment.polarity  # -1 a +1
            
            # Ensemble: média ponderada
            combined = (vader_compound * 0.6) + (textblob_polarity * 0.4)
            
            return max(-1, min(1, combined))  # Clamp to [-1, 1]
        except Exception as e:
            logger.error(f"Erro ao analisar sentimento: {e}")
            return 0.0
    
    def fetch_twitter_sentiment(self, term: str) -> float:
        """Coleta sentimento do Twitter via API (v2)"""
        if not TWITTER_BEARER:
            logger.warning("Twitter API não configurada")
            return 0.0
        
        try:
            import tweepy
            
            client = tweepy.Client(bearer_token=TWITTER_BEARER)
            
            query = f"{term} -is:retweet lang:en"
            tweets = client.search_recent_tweets(
                query=query,
                max_results=100,
                tweet_fields=['created_at', 'public_metrics']
            )
            
            if not tweets.data:
                return 0.0
            
            sentiments = [self.get_sentiment_score(tweet.text) for tweet in tweets.data]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            
            logger.info(f"Twitter ({term}): {avg_sentiment:.2f}")
            return avg_sentiment
        except Exception as e:
            logger.error(f"Erro ao coletar Twitter: {e}")
            return 0.0
    
    def fetch_reddit_sentiment(self, term: str) -> float:
        """Coleta sentimento do Reddit via API (PRAW)"""
        if not REDDIT_CLIENT or not REDDIT_SECRET:
            logger.warning("Reddit API não configurada")
            return 0.0
        
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT,
                client_secret=REDDIT_SECRET,
                user_agent="sentinel-arbitrage-bot"
            )
            
            sentiments = []
            subreddits = ["cryptocurrency", "bitcoin", "ethereum", "solana", "defi", "wallstreetbets"]
            
            for subreddit_name in subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    for submission in subreddit.search(term, time_filter="day", limit=10):
                        sentiment = self.get_sentiment_score(submission.title)
                        sentiments.append(sentiment)
                except Exception as e:
                    logger.debug(f"Erro ao processar subreddit {subreddit_name}: {e}")
                    continue
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            logger.info(f"Reddit ({term}): {avg_sentiment:.2f}")
            return avg_sentiment
        except Exception as e:
            logger.error(f"Erro ao coletar Reddit: {e}")
            return 0.0
    
    def fetch_telegram_sentiment(self, term: str) -> float:
        """Coleta sentimento do Telegram (opcional, requer setup)"""
        if not TELEGRAM_ID or not TELEGRAM_HASH:
            logger.warning("Telegram API não configurada")
            return 0.0
        
        try:
            # Implementação simplificada: seria necessário Telethon setup completo
            # Para produção, integrar com bot de Telegram monitorando canais específicos
            logger.debug(f"Telegram sentiment para {term}: skipped (requer setup adicional)")
            return 0.0
        except Exception as e:
            logger.error(f"Erro ao coletar Telegram: {e}")
            return 0.0
    
    def fetch_news_sentiment(self, term: str) -> float:
        """Coleta sentimento de notícias via NewsAPI"""
        if not NEWSAPI_KEY:
            logger.warning("NewsAPI não configurada")
            return 0.0
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": term,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 50,
                "apiKey": NEWSAPI_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            articles = response.json().get("articles", [])
            
            sentiments = []
            for article in articles:
                text = article.get("title", "") + " " + article.get("description", "")
                sentiment = self.get_sentiment_score(text)
                sentiments.append(sentiment)
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            logger.info(f"News ({term}): {avg_sentiment:.2f}")
            return avg_sentiment
        except Exception as e:
            logger.error(f"Erro ao coletar notícias: {e}")
            return 0.0
    
    def get_aggregated_sentiment(self, term: str, use_cache: bool = True) -> float:
        """
        Agrega sentimento de múltiplas fontes com pesos configuráveis
        Retorna score entre -1 e +1
        """
        # Verifica cache
        if use_cache and term in self.cache:
            if time.time() - self.cache_timestamp.get(term, 0) < CACHE_SENTIMENTO_TTL:
                logger.debug(f"Retornando {term} do cache")
                return self.cache[term]
        
        logger.info(f"Coletando sentimento para {term}...")
        
        # Coleta de múltiplas fontes (pode ser assíncrono em produção)
        sentiments = {
            "twitter": self.fetch_twitter_sentiment(term),
            "reddit": self.fetch_reddit_sentiment(term),
            "telegram": self.fetch_telegram_sentiment(term),
            "news": self.fetch_news_sentiment(term),
        }
        
        # Agrega com pesos
        weighted_sentiment = sum(
            sentiments.get(source, 0.0) * SENTIMENT_WEIGHTS.get(source, 0.0)
            for source in SENTIMENT_WEIGHTS.keys()
        )
        
        # Clamp to [-1, 1]
        final_sentiment = max(-1, min(1, weighted_sentiment))
        
        # Cacheia resultado
        self.cache[term] = final_sentiment
        self.cache_timestamp[term] = time.time()
        
        logger.info(f"Sentimento agregado para {term}: {final_sentiment:.3f}")
        logger.debug(f"Breakdown: {sentiments}")
        
        return final_sentiment
    
    def analyze_all_markets(self) -> Dict[str, float]:
        """Analisa sentimento de todos os mercados configurados"""
        results = {}
        for market in MERCADOS:
            results[market] = self.get_aggregated_sentiment(market)
        return results
    
    def clear_cache(self):
        """Limpa cache de sentimento"""
        self.cache.clear()
        self.cache_timestamp.clear()
