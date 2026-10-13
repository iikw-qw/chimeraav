"""Управление iPhone через Appium."""

from typing import Optional, Dict, Any


class IOSController:
    def __init__(self, udid: str, appium_url: str = "http://localhost:4723"):
        from appium import webdriver
        from appium.options.ios import XCUITestOptions

        opts = XCUITestOptions()
        opts.udid = udid
        opts.platform_name = "iOS"
        self.udid = udid
        self.driver = webdriver.Remote(appium_url, options=opts)

    def tap(self, x: int, y: int):
        from appium.webdriver.common.touch_action import TouchAction
        TouchAction(self.driver).tap(x=x, y=y).perform()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, dur: int = 500):
        self.driver.swipe(x1, y1, x2, y2, dur)

    def find_by_text(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            el = self.driver.find_element("accessibility id", text)
            loc = el.location
            return {"x": loc["x"], "y": loc["y"]}
        except Exception:
            return None

    def find_by_xpath(self, xpath: str) -> Optional[Dict[str, Any]]:
        try:
            el = self.driver.find_element("xpath", xpath)
            loc = el.location
            return {"x": loc["x"], "y": loc["y"]}
        except Exception:
            return None

    def type_text(self, text: str):
        el = self.driver.switch_to.active_element
        el.send_keys(text)

    def screenshot(self) -> bytes:
        return self.driver.get_screenshot_as_png()

    def scroll_down(self, distance: int = 500):
        size = self.driver.get_window_size()
        cx = size["width"] // 2
        sy = size["height"] * 3 // 4
        ey = sy - distance
        self.swipe(cx, sy, cx, ey, 400)

    def scroll_up(self, distance: int = 500):
        size = self.driver.get_window_size()
        cx = size["width"] // 2
        sy = size["height"] // 4
        ey = sy + distance
        self.swipe(cx, sy, cx, ey, 400)

    def press_back(self):
        try:
            el = self.driver.find_element("accessibility id", "Back")
            el.click()
        except Exception:
            pass

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
