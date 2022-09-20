import httpx


class ZarinPal:
    """ZarinPal transaction class"""

    PAYMENT_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
    VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
    START_PAY_URL = "https://www.zarinpal.com/pg/StartPay/"
    MERCHANT_ID = "67b4ca7f-e25f-4d39-bfb8-cdd4f39377f4"

    async def pay(
            self,
            amount: int,
            description: str,
    ):
        async with httpx.AsyncClient() as client:
            request = await client.post(
                f"{self.PAYMENT_URL}?merchant_id={self.MERCHANT_ID}&amount={amount}"
                f"&description={description}&callback_url={self.REDIRECT_URI}"
            )
            if request.status_code == 200 and request.json().get("data") and not \
                    request.json().get("errors") and request.json().get("data").get("code") == 100:
                return f"{self.START_PAY_URL}{request.json().get('data').get('authority')}"
            return

    async def verify(
            self,
            authority: str,
            amount: int,
            status_text: str
    ):
        if status_text != "OK":
            return
        async with httpx.AsyncClient() as client:
            request = await client.post(
                f"{self.VERIFY_URL}?merchant_id={self.MERCHANT_ID}"
                f"&amount={amount}&authority={authority}"
            )
            if request.status_code == 200 and request.json().get("data") and not \
                    request.json().get("errors") and request.json().get("data").get("code") == 100:
                return request.json().get('data')
            return
