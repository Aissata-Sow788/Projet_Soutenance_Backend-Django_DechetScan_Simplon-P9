# Paiements d'abonnement collecteur avec PayDunya

Les formules mensuelles sont définies côté Django : Essentiel (5 000 FCFA),
Professionnel (10 000 FCFA) et Entreprise (20 000 FCFA). Un paiement confirmé
ouvre l'accès collecteur pendant 30 jours.

## Configuration

Ajouter les paramètres suivants au `.env` du backend. Ne jamais placer les clés
PayDunya dans Angular ou dans le dépôt :

```dotenv
PAYDUNYA_MASTER_KEY=
PAYDUNYA_PRIVATE_KEY=
PAYDUNYA_TOKEN=
PAYDUNYA_MODE=test
PAYDUNYA_CALLBACK_URL=
NGROK_AGENT_API_URL=http://127.0.0.1:4040/api/tunnels
PAYDUNYA_FRONTEND_URL=http://localhost:4200
PAYDUNYA_STORE_PHONE=
PAYDUNYA_STORE_ADDRESS=Dakar, Senegal
PAYDUNYA_STORE_WEBSITE=http://localhost:4200
```

Créer une application PayDunya en mode test et y renseigner les trois clés
fournies par PayDunya. En développement, installer ngrok depuis
https://ngrok.com/download, configurer son authtoken dans le CLI, puis garder
ce tunnel actif dans un terminal séparé :

```bash
ngrok http 8000
```

En mode test, l'intégration détecte automatiquement dans l'agent local ngrok
(`http://127.0.0.1:4040/api/tunnels`) l'URL HTTPS publique qui pointe sur Django
port 8000 et construit le callback `/api/paydunya/ipn/`. L'URL ngrok active est
utilisée en priorité sur `PAYDUNYA_CALLBACK_URL`; si aucun tunnel n'est détecté,
la valeur configurée est utilisée comme solution de repli. En production, le
callback fixe est utilisé sans interroger ngrok. Le tunnel doit rester actif
pendant les paiements ; une URL ngrok temporaire change après chaque démarrage.

`PAYDUNYA_FRONTEND_URL=http://localhost:4200` convient au retour sur le même
ordinateur. Pour tester le retour depuis un autre appareil, le frontend Angular
doit également être publié à une URL accessible par cet appareil.

L'API utilise l'endpoint sandbox lorsque `PAYDUNYA_MODE=test` et l'endpoint
production lorsque `PAYDUNYA_MODE=live`.
Pour la production, remplacer `PAYDUNYA_MODE=test` par `live`, renseigner les
clés de production et les URLs publiques du frontend et du backend.

La sélection Wave ou Orange Money limite les canaux affichés par la facture
hébergée PayDunya. La sélection PayDunya laisse disponibles les moyens activés
dans la configuration de l'application PayDunya.

Appliquer ensuite la migration Django :

```bash
python manage.py migrate collecteurs
```

Le navigateur est redirigé vers la facture PayDunya. Le retour navigateur ne
suffit pas à activer l'abonnement : Django vérifie le statut de la facture
directement auprès de PayDunya, et l'IPN effectue la même vérification.
