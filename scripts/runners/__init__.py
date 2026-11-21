"""Runners de test de Chorus.

Cada runner fija `CHORUS_DATABASE_URL` a `osap_chorus_test` y lanza pytest desde la
raíz del proyecto, de modo que funcionan con sólo:

    python scripts/runners/run_core_tests.py

No requieren tener la variable de entorno exportada en la shell.
"""
