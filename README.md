# Giada Referral Bot

Flusso:
1. L'utente apre /start.
2. Il bot crea un link d'invito personale al canale @toiettagiadaxx.
3. Gli ingressi effettuati con quel link vengono conteggiati.
4. A 3 ingressi il bot mostra il pulsante per iscriversi al canale.

Variabile d'ambiente richiesta:
BOT_TOKEN = token del bot ottenuto da @BotFather.

IMPORTANTE:
- Non inserire mai BOT_TOKEN nel codice o in GitHub.
- Il bot deve essere amministratore di @toiettagiadaxx con il permesso di gestire i link d'invito.
- Per un uso in produzione è consigliato usare un database persistente (PostgreSQL), perché il disco locale di alcuni hosting può essere effimero.
