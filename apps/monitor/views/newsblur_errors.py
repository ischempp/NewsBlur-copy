from django.shortcuts import render
from django.views import View

from apps.statistics.models import MStatistics

class Errors(View):

    def get(self, request):
        statistics = MStatistics.all()
        data = {
            'feed_success': statistics['feeds_fetched'],
        }
        chart_name = "errors"
        chart_type = "histogram"

        context = {
            "data": data,
            "chart_name": chart_name,
            "chart_type": chart_type,
        }
        return render(request, 'monitor/prometheus_data.html', context)

