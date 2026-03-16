from django.template.loader import render_to_string
from django.utils.html import escape
import os

class HTMLReport:
    """
    Generates HTML reports.
    """

    def __init__(self, title="Report"):
        self.title = title

    def generate_user_analytics_report(self, user_data, template_name="analytics/user_report.html", output_file="user_analytics_report.html"):
        """
        Generates an HTML report for user analytics.
        user_data: A dictionary containing user analytics data.
        """
        context = {
            'title': self.title,
            'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_data': user_data
        }

        # If a template exists, use it. Otherwise, generate a basic HTML.
        try:
            html_content = render_to_string(template_name, context)
        except:
            html_content = self._default_user_analytics_template(context)

        with open(output_file, 'w') as f:
            f.write(html_content)

        return output_file

    def generate_revenue_report(self, revenue_data, template_name="analytics/revenue_report.html", output_file="revenue_report.html"):
        """
        Generates an HTML report for revenue analytics.
        revenue_data: A dictionary containing revenue analytics data.
        """
        context = {
            'title': "Revenue Report",
            'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'revenue_data': revenue_data
        }

        try:
            html_content = render_to_string(template_name, context)
        except:
            html_content = self._default_revenue_template(context)

        with open(output_file, 'w') as f:
            f.write(html_content)

        return output_file

    def _default_user_analytics_template(self, context):
        """
        Default template for user analytics report.
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{escape(context['title'])}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333366; }}
                h2 {{ color: #666699; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                th {{ background-color: #366092; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>{escape(context['title'])}</h1>
            <p>Generated on: {escape(context['generated_on'])}</p>
            <h2>Daily Signups</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Signups</th>
                </tr>
        """
        for item in context['user_data'].get('daily_signups', []):
            html += f"""
                <tr>
                    <td>{escape(item['date'])}</td>
                    <td>{escape(item['count'])}</td>
                </tr>
            """
        html += """
            </table>
        </body>
        </html>
        """
        return html

    def _default_revenue_template(self, context):
        """
        Default template for revenue report.
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{escape(context['title'])}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333366; }}
                h2 {{ color: #666699; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                th {{ background-color: #366092; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>{escape(context['title'])}</h1>
            <p>Generated on: {escape(context['generated_on'])}</p>
            <h2>Daily Revenue</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Revenue</th>
                </tr>
        """
        for item in context['revenue_data'].get('daily_revenue', []):
            html += f"""
                <tr>
                    <td>{escape(item['date'])}</td>
                    <td>{escape(item['total'])}</td>
                </tr>
            """
        html += """
            </table>
        </body>
        </html>
        """
        return html