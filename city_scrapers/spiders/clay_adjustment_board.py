from datetime import datetime, timedelta
from collections import defaultdict

import scrapy
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider
from dateutil.relativedelta import relativedelta


class ClayAdjustmentBoardSpider(CityScrapersSpider):
    name = "clay_adjustment_board"
    agency = "Clayton Board of Adjustment"
    timezone = "America/Chicago"
    start_urls = [
        "https://www.claytonmo.gov/government/boards-and-commissions/board-of-adjustment/-selyear-allyear"
    ]

    def __init__(self, *args, **kwargs):
        self.agenda_map = defaultdict(list)
        super().__init__(*args, **kwargs)

    def parse(self, response):
        self._parse_links(response)
        yield from self._parse_meetings_page(response)

    def _parse_meetings_page(self, response):
        today = datetime.now()
        for month_delta in range(-9, 2):
            mo_str = (today + relativedelta(months=month_delta)).strftime("%m")
            year_str = (today + relativedelta(months=month_delta)).strftime("%Y")
            url = (
                "https://www.claytonmo.gov/calendar-6/-seldept-8/"
                "-selcat-149/-curm-{month}/-cury-{year}".format(year=year_str, month=mo_str)
            )
            yield scrapy.Request(url=url, method="GET", callback=self._parse_events_page)

    def _parse_events_page(self, response):
        for url in self._get_event_urls(response):
            yield scrapy.Request(url, callback=self._parse_event, dont_filter=True)

    def _parse_event(self, response):
        """
        `parse` should always `yield` Meeting items.

        Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
        needs.
        """
        title = self._parse_title(response)
        times = self._parse_time(response)
        start = times[0]
        links_key = start.strftime("%m/%d/%Y")
        meeting = Meeting(
            title=title,
            description=self._parse_description(response),
            classification=BOARD,
            start=times[0],
            end=times[1],
            all_day=False,
            time_notes="",
            location=self._parse_location(response),
            links=self.agenda_map[links_key],
            source=response.url,
        )

        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)

        return meeting

    def _get_event_urls(self, response):
        responses = []
        events = response.css("td.calendar_day div.calendar_item")
        for event in events:
            event_title = event.css("a.calendar_eventlink::text").get()
            if "Adjustment" in event_title:
                href = event.css("a.calendar_eventlink::attr(href)").get()
                responses.append(response.urljoin(href))
        return responses

    def _parse_title(self, response):
        """Parse or generate meeting title."""
        return response.css("h2.detail-title span::text").get()

    def _parse_description(self, response):
        """Parse or generate meeting description."""
        return response.css("div.detail-content p::text").get()

    def _parse_time(self, response):
        """Parse start and end datetime as a naive datetime object."""
        dt = response.css("span.detail-list-value::text").get()
        start = datetime.strptime(dt.strip(), "%m/%d/%Y %H:%M %p")
        end = start + timedelta(hours=2)
        return (start, end)

    def _parse_location(self, response):
        """Parse or generate location."""
        text = "Clayton City Hall"
        address = "Clayton City Hall, Second Floor Council Chambers of Clayton located at 10 North Bemiston Avenue"
        return {
            "address": address,
            "name": text,
        }

    # def _get_status(self, item: Mapping, text: str = "") -> str:
    #     """
    #     Generates one of the allowed statuses from constants based on the title and time
    #     of the meeting
    #     """
    #     meeting_text = " ".join(
    #         [item.get("title", ""), item.get("description", ""), text]
    #     ).lower()
    #     if any(word in meeting_text for word in ["cancel", "rescheduled", "postpone", "cancelled", "no meeting"]):
    #         return CANCELLED
    #     if item["start"] < datetime.now():
    #         return PASSED
    #     return TENTATIVE

    def _parse_links(self, response):
        """Parse or generate links."""
        links = response.css("tr.meeting_widget_item")
        for link in links:
            dt = link.css("td.mobile_hide::text").get().split()[0]
            if datetime.strptime(dt.strip(), "%m/%d/%Y"):
                date = datetime.strptime(dt.strip(), "%m/%d/%Y")
            else:
                date = datetime.strptime(dt.strip(), "%m/%d/%Y %H:%M %p")
            for i in link.css("span.detail-list-value"):
                href = i.css("a::attr(href)").get()
                type_ = i.css("a::text").get()
                self.agenda_map[date.strftime("%m/%d/%Y")].append({"href":href, "title":type_})

            ## pages!!!
            # parse -> _parse_num_pages -> _parse_links