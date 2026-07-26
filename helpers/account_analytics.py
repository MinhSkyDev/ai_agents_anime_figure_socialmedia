import os
import sys
import re
import json
import requests
from datetime import datetime
from config import ACCESS_TOKEN, IG_USER_ID

def fetch_and_analyze_account_posts(limit=50):
    """
    Fetches published Instagram posts via Meta Graph API and performs deep performance analytics:
    - Recent Posts Live Feed with individual performance scores
    - Overall Account Health Summary (Total Likes, Comments, Avg Likes)
    - Top 5 Hall-of-Fame Posts
    - Hashtag ROI Ranking (which tags correlate with top 20% engagement)
    - Best Day of Week & Peak Hour Posting Windows based on empirical data
    - Content Pattern Style Performance (Quote/Lyric vs Short 1-liner)
    """
    if not ACCESS_TOKEN or not IG_USER_ID:
        return {
            'success': False,
            'error': 'Missing FB_ACCESS_TOKEN or IG_USER_ID in config/env'
        }

    url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media?fields=id,caption,like_count,comments_count,timestamp,permalink,media_type&limit={limit}&access_token={ACCESS_TOKEN}"

    try:
        res = requests.get(url, timeout=12)
        if res.status_code != 200:
            return {
                'success': False,
                'error': f"Meta Graph API HTTP {res.status_code}: {res.text}"
            }

        data = res.json()
        raw_posts = data.get('data', [])
        
        if not raw_posts:
            return {
                'success': False,
                'error': 'No published posts found on this Instagram account'
            }

        processed_posts = []
        total_likes = 0
        total_comments = 0

        hashtag_engagement = {}
        day_engagement = {}
        hour_engagement = {}

        for p in raw_posts:
            likes = p.get('like_count', 0)
            comments = p.get('comments_count', 0)
            caption = p.get('caption', '').strip()
            permalink = p.get('permalink', '')
            ts_str = p.get('timestamp', '')

            total_likes += likes
            total_comments += comments

            # Parse datetime
            day_name = "Unknown"
            hour_val = 0
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    day_name = dt.strftime('%A')
                    hour_val = dt.hour
                except Exception:
                    pass

            # Classify style pattern
            is_quote = '"' in caption or "…" in caption or "..." in caption or "\n" in caption or any(c in caption for c in ['tình', 'yêu', 'người', 'thương', 'anh', 'em'])
            style_pattern = "Quote / Lyric / Poetic" if is_quote else "Short & Playful 1-Liner"

            # Hashtag frequency & engagement tracking
            tags = [t.lower() for t in re.findall(r'#\w+', caption)] if caption else []
            for t in tags:
                if t not in hashtag_engagement:
                    hashtag_engagement[t] = {'count': 0, 'total_likes': 0}
                hashtag_engagement[t]['count'] += 1
                hashtag_engagement[t]['total_likes'] += likes

            # Day of week engagement tracking
            if day_name not in day_engagement:
                day_engagement[day_name] = {'count': 0, 'total_likes': 0}
            day_engagement[day_name]['count'] += 1
            day_engagement[day_name]['total_likes'] += likes

            # Hour engagement tracking
            hour_str = f"{hour_val:02d}:00 UTC"
            if hour_str not in hour_engagement:
                hour_engagement[hour_str] = {'count': 0, 'total_likes': 0}
            hour_engagement[hour_str]['count'] += 1
            hour_engagement[hour_str]['total_likes'] += likes

            processed_posts.append({
                'id': p.get('id'),
                'caption': caption,
                'like_count': likes,
                'comments_count': comments,
                'style_pattern': style_pattern,
                'timestamp': ts_str,
                'permalink': permalink,
                'hashtags': tags
            })

        avg_likes = round(total_likes / len(processed_posts), 1) if processed_posts else 0
        avg_comments = round(total_comments / len(processed_posts), 1) if processed_posts else 0

        # Top 5 Hall-of-Fame Posts sorted by likes
        top_posts = sorted(processed_posts, key=lambda x: x['like_count'], reverse=True)[:5]

        # Recent 15 Posts Feed
        recent_posts = processed_posts[:15]

        # Hashtag ROI Ranking
        hashtag_ranking = []
        for t, stat in hashtag_engagement.items():
            if stat['count'] >= 2: # Used in at least 2 posts
                avg_tag_likes = round(stat['total_likes'] / stat['count'], 1)
                hashtag_ranking.append({
                    'tag': t,
                    'post_count': stat['count'],
                    'avg_likes': avg_tag_likes
                })
        hashtag_ranking = sorted(hashtag_ranking, key=lambda x: x['avg_likes'], reverse=True)[:10]

        # Best Day of Week
        best_days = []
        for d, stat in day_engagement.items():
            avg_d_likes = round(stat['total_likes'] / stat['count'], 1)
            best_days.append({'day': d, 'avg_likes': avg_d_likes, 'posts': stat['count']})
        best_days = sorted(best_days, key=lambda x: x['avg_likes'], reverse=True)

        # Best Hour
        best_hours = []
        for h, stat in hour_engagement.items():
            avg_h_likes = round(stat['total_likes'] / stat['count'], 1)
            best_hours.append({'hour': h, 'avg_likes': avg_h_likes, 'posts': stat['count']})
        best_hours = sorted(best_hours, key=lambda x: x['avg_likes'], reverse=True)[:5]

        # Style Performance Comparison
        quote_posts = [p for p in processed_posts if p['style_pattern'] == "Quote / Lyric / Poetic"]
        playful_posts = [p for p in processed_posts if p['style_pattern'] == "Short & Playful 1-Liner"]

        avg_quote_likes = round(sum(p['like_count'] for p in quote_posts) / len(quote_posts), 1) if quote_posts else 0
        avg_playful_likes = round(sum(p['like_count'] for p in playful_posts) / len(playful_posts), 1) if playful_posts else 0

        verdict = f"Quotes/Lyrics style averages {avg_quote_likes} likes vs Playful 1-Liners averaging {avg_playful_likes} likes."

        return {
            'success': True,
            'summary': {
                'total_posts': len(processed_posts),
                'total_likes': total_likes,
                'total_comments': total_comments,
                'avg_likes_per_post': avg_likes,
                'avg_comments_per_post': avg_comments
            },
            'recent_posts': recent_posts,
            'top_posts': top_posts,
            'hashtag_roi': hashtag_ranking,
            'best_days': best_days,
            'best_hours': best_hours,
            'style_comparison': {
                'quote_style_avg_likes': avg_quote_likes,
                'playful_style_avg_likes': avg_playful_likes,
                'verdict': verdict
            }
        }

    except Exception as e:
        print(f"[Analytics Error] {e}")
        return {
            'success': False,
            'error': str(e)
        }
