Pretix SumUp Payment Plugin
============================

Accept credit card payments via SumUp.

Features
--------

- Credit card payments via SumUp's card widget
- Alternative Payment Methods (Apple Pay, Google Pay, iDEAL, etc.)
- Inline payment form (no redirect)
- Automatic payment status synchronization via webhooks
- Payment reconciliation tools
- Admin diagnostics UI for webhooks
- Structured logging for operational visibility

Setup
-----

1. Install the plugin::

    pip install pretix-sumup-payment

2. Enable the plugin in Pretix admin ("Settings" → "Plugins").

3. Configure the payment provider under your event's settings
   ("Settings" → "Payment" → "SumUp").

4. Enter your SumUp API Key (sup_sk_...).

5. The merchant code and name will be auto-filled from the API.

6. Optionally enable Alternative Payment Methods and/or Google Pay.

7. Configure your SumUp webhook to point at::

    https://your-domain.com/pretix/<org>/<event>/sumup/checkout_event/<payment_id>/

   The webhook URL is unique per event and payment. Configure it in your
   SumUp developer dashboard under Webhooks.

For more detailed setup instructions, see:
- Architecture: `docs/ARCHITECTURE.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Development: `README.dev.md`

Google Pay Setup
----------------

1. Register at https://pay.google.com/business/console/
2. Get your Google Merchant ID
3. Enable Google Pay in the plugin settings
4. Contact SumUp to activate Google Pay on your account

See the plugin settings help text for detailed step-by-step instructions.

Development
-----------

For local development with Docker:

.. code-block:: bash

    git clone https://github.com/wiomoc/pretix-sumup-payment.git
    cd pretix-sumup-payment
    docker compose build
    docker compose up -d
    docker compose exec pretix python -m pretix migrate
    docker compose exec pretix python -m pretix createsuperuser

See `README.dev.md` for detailed development instructions.

Running tests:

.. code-block:: bash

    pip install -e .
    pip install pytest pytest-django
    py.test tests

License
-------

Apache 2.0
