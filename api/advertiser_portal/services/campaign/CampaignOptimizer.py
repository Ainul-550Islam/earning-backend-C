"""
Campaign Optimizer Service

Service for automatic campaign optimization,
including bid adjustments and performance-based optimization.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.db.models import Avg, Sum, Count, Q

from ...models.campaign import AdCampaign, CampaignBid
from ...models.reporting import CampaignReport
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class CampaignOptimizer:
    """
    Service for automatic campaign optimization.
    
    Handles bid adjustments, performance analysis,
    and optimization recommendations.
    """
    
    def __init__(self):
        self.logger = logger
    
    def optimize_campaign_bid(self, campaign: AdCampaign) -> Dict[str, Any]:
        """
        Optimize campaign bid based on performance.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Dict[str, Any]: Optimization results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Get campaign bid configuration
                bid_config = getattr(campaign, 'bid', None)
                if not bid_config or not bid_config.auto_optimize:
                    return {
                        'optimized': False,
                        'reason': 'Auto-optimization not enabled',
                        'old_bid': bid_config.bid_amount if bid_config else None,
                        'new_bid': bid_config.bid_amount if bid_config else None,
                    }
                
                # Get performance data
                performance_data = self._get_campaign_performance(campaign, days=7)
                
                # Calculate optimization recommendations
                optimization_result = self._calculate_bid_optimization(bid_config, performance_data)
                
                # Apply optimization if recommended
                if optimization_result['should_adjust']:
                    old_bid = bid_config.bid_amount
                    bid_config.bid_amount = optimization_result['recommended_bid']
                    bid_config.save()
                    
                    # Send notification
                    self._send_bid_optimization_notification(campaign, old_bid, bid_config.bid_amount, optimization_result)
                    
                    self.logger.info(f"Optimized bid for campaign: {campaign.name} - {old_bid} -> {bid_config.bid_amount}")
                
                return optimization_result
                
        except Exception as e:
            self.logger.error(f"Error optimizing campaign bid: {e}")
            raise ValidationError(f"Failed to optimize campaign bid: {str(e)}")
    
    def optimize_all_campaigns(self) -> Dict[str, Any]:
        """
        Optimize all campaigns with auto-optimization enabled.
        
        Returns:
            Dict[str, Any]: Optimization results summary
        """
        try:
            campaigns_with_optimization = AdCampaign.objects.filter(
                bid__auto_optimize=True,
                status='active'
            ).select_related('bid', 'advertiser')
            
            optimized_count = 0
            skipped_count = 0
            errors = []
            
            for campaign in campaigns_with_optimization:
                try:
                    result = self.optimize_campaign_bid(campaign)
                    if result['optimized']:
                        optimized_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append({
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'error': str(e)
                    })
            
            return {
                'campaigns_processed': campaigns_with_optimization.count(),
                'optimized_count': optimized_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'timestamp': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing all campaigns: {e}")
            raise ValidationError(f"Failed to optimize campaigns: {str(e)}")
    
    def get_optimization_recommendations(self, campaign: AdCampaign) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations for campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            List[Dict[str, Any]]: Optimization recommendations
        """
        try:
            recommendations = []
            
            # Get performance data
            performance_data = self._get_campaign_performance(campaign, days=14)
            
            # Analyze performance and generate recommendations
            bid_recommendations = self._analyze_bid_performance(campaign, performance_data)
            targeting_recommendations = self._analyze_targeting_performance(campaign, performance_data)
            creative_recommendations = self._analyze_creative_performance(campaign, performance_data)
            budget_recommendations = self._analyze_budget_performance(campaign, performance_data)
            
            recommendations.extend(bid_recommendations)
            recommendations.extend(targeting_recommendations)
            recommendations.extend(creative_recommendations)
            recommendations.extend(budget_recommendations)
            
            # Sort by priority
            recommendations.sort(key=lambda x: x.get('priority', 'medium'), reverse=True)
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting optimization recommendations: {e}")
            return []
    
    def apply_optimization_recommendation(self, campaign: AdCampaign, recommendation_id: str) -> Dict[str, Any]:
        """
        Apply a specific optimization recommendation.
        
        Args:
            campaign: Campaign instance
            recommendation_id: ID of recommendation to apply
            
        Returns:
            Dict[str, Any]: Application result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                recommendations = self.get_optimization_recommendations(campaign)
                
                # Find the recommendation
                recommendation = None
                for rec in recommendations:
                    if rec.get('id') == recommendation_id:
                        recommendation = rec
                        break
                
                if not recommendation:
                    raise ValidationError("Recommendation not found")
                
                # Apply the recommendation based on type
                result = self._apply_recommendation(campaign, recommendation)
                
                # Send notification
                self._send_recommendation_applied_notification(campaign, recommendation)
                
                self.logger.info(f"Applied optimization recommendation: {recommendation['type']} for {campaign.name}")
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error applying optimization recommendation: {e}")
            raise ValidationError(f"Failed to apply recommendation: {str(e)}")
    
    def get_performance_insights(self, campaign: AdCampaign, days: int = 30) -> Dict[str, Any]:
        """
        Get performance insights for campaign.
        
        Args:
            campaign: Campaign instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Performance insights
        """
        try:
            performance_data = self._get_campaign_performance(campaign, days)
            
            insights = {
                'overall_performance': self._analyze_overall_performance(performance_data),
                'trend_analysis': self._analyze_performance_trends(performance_data),
                'efficiency_metrics': self._analyze_efficiency_metrics(performance_data),
                'comparison_analysis': self._analyze_performance_comparison(campaign, performance_data),
                'recommendations': self.get_optimization_recommendations(campaign),
            }
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting performance insights: {e}")
            raise ValidationError(f"Failed to get insights: {str(e)}")
    
    def _get_campaign_performance(self, campaign: AdCampaign, days: int) -> Dict[str, Any]:
        """Get campaign performance data."""
        from ...models.reporting import CampaignReport
        
        start_date = timezone.now().date() - timezone.timedelta(days=days)
        
        reports = CampaignReport.objects.filter(
            campaign=campaign,
            date__gte=start_date
        ).aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_spend=Sum('spend_amount'),
            avg_ctr=Avg('ctr'),
            avg_conversion_rate=Avg('conversion_rate'),
            avg_cpa=Avg('cpa'),
            avg_cpc=Avg('cpc'),
            days_with_data=Count('date')
        )
        
        # Fill missing values with 0
        for key, value in reports.items():
            if value is None:
                reports[key] = 0
        
        # Calculate derived metrics
        total_impressions = reports['total_impressions']
        total_clicks = reports['total_clicks']
        total_conversions = reports['total_conversions']
        total_spend = reports['total_spend']
        
        calculated_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        calculated_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
        calculated_cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
        
        return {
            'period_days': days,
            'days_with_data': reports['days_with_data'],
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'total_spend': total_spend,
            'ctr': calculated_ctr,
            'cpc': calculated_cpc,
            'cpa': calculated_cpa,
            'avg_ctr': reports['avg_ctr'],
            'avg_conversion_rate': reports['avg_conversion_rate'],
            'avg_cpa': reports['avg_cpa'],
            'avg_cpc': reports['avg_cpc'],
        }
    
    def _calculate_bid_optimization(self, bid_config: CampaignBid, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate bid optimization recommendations."""
        current_bid = bid_config.bid_amount
        bid_type = bid_config.bid_type
        
        optimization = {
            'should_adjust': False,
            'recommended_bid': current_bid,
            'adjustment_type': 'none',
            'adjustment_reason': '',
            'confidence': 0.0,
            'optimized': False,
        }
        
        if bid_type == 'cpc':
            optimization = self._optimize_cpc_bid(bid_config, performance_data)
        elif bid_type == 'cpa':
            optimization = self._optimize_cpa_bid(bid_config, performance_data)
        elif bid_type == 'cpm':
            optimization = self._optimize_cpm_bid(bid_config, performance_data)
        
        return optimization
    
    def _optimize_cpc_bid(self, bid_config: CampaignBid, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize CPC bid based on performance."""
        current_bid = bid_config.bid_amount
        current_cpc = performance_data['cpc']
        target_cpc = performance_data['avg_cpc']
        
        optimization = {
            'should_adjust': False,
            'recommended_bid': current_bid,
            'adjustment_type': 'none',
            'adjustment_reason': '',
            'confidence': 0.0,
            'optimized': False,
        }
        
        # If current CPC is significantly higher than target, reduce bid
        if current_cpc > target_cpc * 1.2:
            recommended_bid = current_bid * 0.9  # Reduce by 10%
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'decrease',
                'adjustment_reason': f'Current CPC (${current_cpc:.3f}) is 20% higher than target (${target_cpc:.3f})',
                'confidence': 0.8,
                'optimized': True,
            })
        
        # If current CPC is significantly lower than target, increase bid
        elif current_cpc < target_cpc * 0.8 and performance_data['total_clicks'] < 100:
            recommended_bid = current_bid * 1.1  # Increase by 10%
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'increase',
                'adjustment_reason': f'Current CPC (${current_cpc:.3f}) is 20% lower than target (${target_cpc:.3f})',
                'confidence': 0.7,
                'optimized': True,
            })
        
        return optimization
    
    def _optimize_cpa_bid(self, bid_config: CampaignBid, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize CPA bid based on performance."""
        current_bid = bid_config.bid_amount
        current_cpa = performance_data['cpa']
        
        optimization = {
            'should_adjust': False,
            'recommended_bid': current_bid,
            'adjustment_type': 'none',
            'adjustment_reason': '',
            'confidence': 0.0,
            'optimized': False,
        }
        
        # If CPA is too high and conversions are low, reduce bid
        if current_cpa > current_bid * 1.5 and performance_data['total_conversions'] < 10:
            recommended_bid = current_bid * 0.85  # Reduce by 15%
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'decrease',
                'adjustment_reason': f'Current CPA (${current_cpa:.2f}) is 50% higher than bid (${current_bid:.2f})',
                'confidence': 0.8,
                'optimized': True,
            })
        
        # If CPA is good and volume is low, increase bid
        elif current_cpa < current_bid * 0.8 and performance_data['total_conversions'] < 5:
            recommended_bid = current_bid * 1.15  # Increase by 15%
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'increase',
                'adjustment_reason': f'Good CPA (${current_cpa:.2f}) but low volume, consider increasing bid',
                'confidence': 0.6,
                'optimized': True,
            })
        
        return optimization
    
    def _optimize_cpm_bid(self, bid_config: CampaignBid, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize CPM bid based on performance."""
        current_bid = bid_config.bid_amount
        current_cpm = (performance_data['total_spend'] / performance_data['total_impressions'] * 1000) if performance_data['total_impressions'] > 0 else 0
        
        optimization = {
            'should_adjust': False,
            'recommended_bid': current_bid,
            'adjustment_type': 'none',
            'adjustment_reason': '',
            'confidence': 0.0,
            'optimized': False,
        }
        
        # Simple CPM optimization based on CTR
        ctr = performance_data['ctr']
        
        if ctr < 0.5:  # Low CTR, reduce bid
            recommended_bid = current_bid * 0.9
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'decrease',
                'adjustment_reason': f'Low CTR ({ctr:.2f}%), consider reducing bid',
                'confidence': 0.7,
                'optimized': True,
            })
        
        elif ctr > 2.0:  # High CTR, increase bid
            recommended_bid = current_bid * 1.1
            optimization.update({
                'should_adjust': True,
                'recommended_bid': recommended_bid,
                'adjustment_type': 'increase',
                'adjustment_reason': f'High CTR ({ctr:.2f}%), consider increasing bid',
                'confidence': 0.6,
                'optimized': True,
            })
        
        return optimization
    
    def _analyze_bid_performance(self, campaign: AdCampaign, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze bid performance and generate recommendations."""
        recommendations = []
        
        bid_config = getattr(campaign, 'bid', None)
        if not bid_config:
            return recommendations
        
        # Check if bid is too high
        if bid_config.bid_type == 'cpc' and performance_data['cpc'] > bid_config.bid_amount * 1.3:
            recommendations.append({
                'id': f'bid_reduce_{campaign.id}',
                'type': 'bid_adjustment',
                'priority': 'high',
                'title': _('Reduce Bid to Improve ROI'),
                'description': _('Current CPC is 30% higher than your bid. Consider reducing bid.'),
                'action': 'reduce_bid',
                'suggested_value': bid_config.bid_amount * 0.9,
                'current_value': bid_config.bid_amount,
            })
        
        # Check if bid is too low
        if bid_config.bid_type == 'cpc' and performance_data['total_clicks'] < 50:
            recommendations.append({
                'id': f'bid_increase_{campaign.id}',
                'type': 'bid_adjustment',
                'priority': 'medium',
                'title': _('Increase Bid for More Traffic'),
                'description': _('Low click volume suggests bid may be too low.'),
                'action': 'increase_bid',
                'suggested_value': bid_config.bid_amount * 1.2,
                'current_value': bid_config.bid_amount,
            })
        
        return recommendations
    
    def _analyze_targeting_performance(self, campaign: AdCampaign, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze targeting performance and generate recommendations."""
        recommendations = []
        
        # Check conversion rate
        if performance_data['avg_conversion_rate'] < 1.0:
            recommendations.append({
                'id': f'targeting_refine_{campaign.id}',
                'type': 'targeting_adjustment',
                'priority': 'medium',
                'title': _('Refine Targeting to Improve Conversion Rate'),
                'description': _('Low conversion rate suggests targeting may be too broad.'),
                'action': 'refine_targeting',
                'suggested_changes': ['narrow_geography', 'add_device_filters', 'refine_keywords'],
            })
        
        return recommendations
    
    def _analyze_creative_performance(self, campaign: AdCampaign, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze creative performance and generate recommendations."""
        recommendations = []
        
        # Check CTR
        if performance_data['ctr'] < 1.0:
            recommendations.append({
                'id': f'creative_optimize_{campaign.id}',
                'type': 'creative_optimization',
                'priority': 'medium',
                'title': _('Optimize Creatives to Improve CTR'),
                'description': _('Low CTR suggests creatives may need improvement.'),
                'action': 'optimize_creatives',
                'suggested_changes': ['test_new_headlines', 'update_images', 'improve_cta'],
            })
        
        return recommendations
    
    def _analyze_budget_performance(self, campaign: AdCampaign, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze budget performance and generate recommendations."""
        recommendations = []
        
        # Check if budget is underutilized
        if campaign.budget_daily and performance_data['total_spend'] < campaign.budget_daily * 0.5:
            recommendations.append({
                'id': f'budget_adjust_{campaign.id}',
                'type': 'budget_adjustment',
                'priority': 'low',
                'title': _('Consider Adjusting Budget'),
                'description': _('Daily budget is underutilized. Consider reducing or increasing to maximize performance.'),
                'action': 'adjust_budget',
                'suggested_value': performance_data['total_spend'] * 1.2,
                'current_value': campaign.budget_daily,
            })
        
        return recommendations
    
    def _apply_recommendation(self, campaign: AdCampaign, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a specific optimization recommendation."""
        action = recommendation['action']
        
        if action == 'reduce_bid' or action == 'increase_bid':
            bid_config = getattr(campaign, 'bid', None)
            if bid_config:
                old_bid = bid_config.bid_amount
                bid_config.bid_amount = recommendation['suggested_value']
                bid_config.save()
                
                return {
                    'applied': True,
                    'old_value': old_bid,
                    'new_value': bid_config.bid_amount,
                    'action': action,
                }
        
        elif action == 'adjust_budget':
            old_budget = campaign.budget_daily
            campaign.budget_daily = recommendation['suggested_value']
            campaign.save()
            
            return {
                'applied': True,
                'old_value': old_budget,
                'new_value': campaign.budget_daily,
                'action': action,
            }
        
        return {
            'applied': False,
            'reason': 'Action not implemented',
            'action': action,
        }
    
    def _analyze_overall_performance(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall campaign performance."""
        return {
            'performance_score': self._calculate_performance_score(performance_data),
            'key_metrics': {
                'ctr': performance_data['ctr'],
                'cpa': performance_data['cpa'],
                'conversions': performance_data['total_conversions'],
                'spend': performance_data['total_spend'],
            },
            'trend': 'stable',  # Would calculate from historical data
            'efficiency': 'good' if performance_data['cpa'] < performance_data['avg_cpa'] else 'poor',
        }
    
    def _analyze_performance_trends(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance trends."""
        return {
            'ctr_trend': 'stable',
            'cpa_trend': 'improving',
            'volume_trend': 'increasing',
            'efficiency_trend': 'stable',
        }
    
    def _analyze_efficiency_metrics(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze efficiency metrics."""
        return {
            'cost_efficiency': performance_data['cpa'] / performance_data['avg_cpa'] if performance_data['avg_cpa'] > 0 else 1,
            'volume_efficiency': performance_data['total_conversions'] / performance_data['period_days'],
            'budget_efficiency': performance_data['total_spend'] / (performance_data['period_days'] * 100),  # Placeholder
        }
    
    def _analyze_performance_comparison(self, campaign: AdCampaign, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance compared to similar campaigns."""
        return {
            'percentile_rank': 75,  # Would calculate from similar campaigns
            'performance_vs_average': 'above_average',
            'key_strengths': ['low_cpa', 'high_ctr'],
            'improvement_areas': ['volume', 'reach'],
        }
    
    def _calculate_performance_score(self, performance_data: Dict[str, Any]) -> float:
        """Calculate overall performance score."""
        # Simple scoring algorithm
        ctr_score = min(performance_data['ctr'] / 2.0 * 100, 100)  # 2% CTR = 100 points
        cpa_score = max(100 - (performance_data['cpa'] / performance_data['avg_cpa'] - 1) * 100, 0) if performance_data['avg_cpa'] > 0 else 50
        volume_score = min(performance_data['total_conversions'] / 10 * 100, 100)  # 10 conversions = 100 points
        
        return (ctr_score + cpa_score + volume_score) / 3
    
    def _send_bid_optimization_notification(self, campaign: AdCampaign, old_bid: float, new_bid: float, result: Dict[str, Any]):
        """Send bid optimization notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_started',
            title=_('Campaign Bid Optimized'),
            message=_(
                'Your campaign "{campaign_name}" bid has been automatically optimized '
                'from ${old_bid:.3f} to ${new_bid:.3f}. Reason: {reason}'
            ).format(
                campaign_name=campaign.name,
                old_bid=old_bid,
                new_bid=new_bid,
                reason=result['adjustment_reason']
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/bid/',
            action_text=_('View Bid Settings')
        )
    
    def _send_recommendation_applied_notification(self, campaign: AdCampaign, recommendation: Dict[str, Any]):
        """Send recommendation applied notification."""
        AdvertiserNotification.objects.create(
            advertiser=campaign.advertiser,
            type='campaign_started',
            title=_('Optimization Applied'),
            message=_(
                'Optimization recommendation "{title}" has been applied to your campaign "{campaign_name}".'
            ).format(
                title=recommendation['title'],
                campaign_name=campaign.name
            ),
            priority='medium',
            action_url=f'/advertiser/campaigns/{campaign.id}/',
            action_text=_('View Campaign')
        )
