# Gestion de fournisseurs

Application web de gestion des fournisseurs, commandes d'achat, factures,
paiements et rapports. Le backend expose une API Django REST Framework protégée
par JWT ; le frontend React/Vite communique avec cette API.

## Fonctionnalités

- Tableau de bord avec indicateurs, alertes et graphiques.
- Gestion des fournisseurs, demandes et comparaisons de devis, commandes,
  réceptions de livraison, factures et paiements.
- Rôles `ADMINISTRATEUR` et `ACHETEUR`, inscription publique limitée au rôle
  acheteur et journal d'audit réservé aux administrateurs.
- Workflow de commande avec brouillon, soumission, validation ou refus
  administratif motivé ; suivi des réceptions partielles et complètes.
- Évaluations fournisseurs fondées sur des commandes entièrement livrées.
- PDF des bons de commande, exports PDF/XLSX des rapports et sauvegarde MySQL.
- Documentation interactive de l'API via OpenAPI/Swagger.

## Prérequis

- Python 3.11 ou plus récent.
- MySQL 8.x (ou une version compatible avec `mysqlclient`).
- Node.js 20 ou plus récent et npm.
- `mysqldump` et `mysql` installés pour sauvegarder et restaurer la base.

Sous Windows, l'installation de `mysqlclient` peut nécessiter les outils de
compilation C++ de Visual Studio si aucun paquet binaire compatible n'est
disponible.

## Installation locale sous Windows

Depuis le dossier du projet, créez l'environnement Python et installez les
dépendances :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Créez une base MySQL et un utilisateur ayant les droits nécessaires sur cette
base. Copiez ensuite le modèle de configuration et créez une clé secrète :

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Collez la clé produite dans `SECRET_KEY` et renseignez `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST` et `DB_PORT` dans `.env`. Pour le développement local,
`DEBUG=True`, `ALLOWED_HOSTS=localhost,127.0.0.1` et l'origine CORS fournie dans
`.env.example` conviennent.

Appliquez les migrations et démarrez l'API :

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py runserver
```

L'API est disponible sur `http://127.0.0.1:8000/api/` et sa documentation sur
`http://127.0.0.1:8000/api/docs/`.

Dans un second terminal, installez et lancez le frontend :

```powershell
Set-Location frontend
npm install
npm run dev
```

Ouvrez l'adresse Vite indiquée dans le terminal (par défaut
`http://localhost:5173`). Le serveur Vite transmet les requêtes `/api` au backend
sur `http://127.0.0.1:8000`.

## Comptes et données de démonstration

Pour une base locale de démonstration, exécutez depuis `backend` :

```powershell
..\.venv\Scripts\python.exe manage.py seed_demo
```

La commande demande un mot de passe distinct pour chaque compte créé et le
confirme sans l'afficher. Elle crée un administrateur `demo_admin`, un acheteur
`demo_buyer`, deux fournisseurs, deux commandes, une facture et un paiement
partiel. Elle peut être relancée sans dupliquer les données. Si ces noms
d'utilisateur existent déjà avec un rôle différent ou sont désactivés, la
commande s'arrête plutôt que de modifier leur accès. Les options
`--admin-password` et `--buyer-password` sont disponibles pour l'automatisation,
mais les mots de passe passés en arguments peuvent être visibles dans la liste
des processus.

**N'exécutez pas le seed de démonstration sur une base de production.** Aucun
mot de passe de démonstration par défaut n'est fourni.

Pour créer le premier compte d'administration d'une installation réelle,
utilisez `createsuperuser`, puis attribuez-lui explicitement le rôle métier
administrateur :

```powershell
..\.venv\Scripts\python.exe manage.py createsuperuser
..\.venv\Scripts\python.exe manage.py shell -c "from accounts.models import User; User.objects.filter(username='VOTRE_IDENTIFIANT').update(role=User.Role.ADMINISTRATEUR)"
```

Remplacez `VOTRE_IDENTIFIANT` par l'identifiant créé. Les comptes acheteurs
peuvent ensuite s'inscrire depuis le bouton d'inscription de la page de
connexion.

## Tests et vérifications

Les tests backend utilisent SQLite en mémoire, afin de pouvoir valider les
modèles, les permissions, le seed et les calculs sans serveur MySQL :

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py test --settings=config.test_settings
..\.venv\Scripts\python.exe manage.py check --settings=config.test_settings
..\.venv\Scripts\python.exe manage.py spectacular --validate --settings=config.test_settings
```

Les vérifications frontend :

```powershell
Set-Location frontend
npm run lint
npm run build
```

## Configuration

Toutes les variables sont documentées dans [.env.example](./.env.example).
Les principales sont :

| Variable | Rôle |
| --- | --- |
| `SECRET_KEY` | Clé secrète Django, obligatoire et privée. |
| `DEBUG` | Mode debug ; doit être `False` en production. |
| `ALLOWED_HOSTS` | Hôtes autorisés par Django, séparés par des virgules. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Connexion MySQL. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Origines frontend autorisées. |
| `BACKUP_DIR`, `MYSQLDUMP_PATH` | Destination des sauvegardes et chemin de `mysqldump`. |
| `COMPANY_NAME`, `COMPANY_ADDRESS`, `COMPANY_EMAIL`, `COMPANY_PHONE`, `COMPANY_TAX_ID` | Informations imprimées sur les bons de commande. |
| `TIME_ZONE` | Fuseau horaire applicatif. |

Ne versionnez jamais `.env`. En production, configurez HTTPS et les domaines
réels, gardez `DEBUG=False`, utilisez des secrets uniques, limitez l'accès
réseau à MySQL et protégez/chiffrez les sauvegardes conformément à votre
politique de rétention.

## Sauvegardes MySQL

La commande `python manage.py backup_db` crée un dump SQL horodaté dans
`BACKUP_DIR`. Un administrateur peut également lancer une sauvegarde depuis
l'espace de gestion des utilisateurs. Pour la restauration, la planification
et les précautions de sécurité, consultez
[backend/BACKUP.md](./backend/BACKUP.md).

## Devis, commandes et livraisons

Les demandes de devis regroupent plusieurs fournisseurs pour un même produit
ou service et permettent de saisir manuellement les prix, délais, évaluations
de qualité et conditions de paiement reçus. L'application n'envoie pas ces
demandes par e-mail.

Une commande est créée comme brouillon. Son créateur peut la soumettre ; seul
un administrateur distinct de ce créateur peut ensuite l'approuver ou la
refuser. Le motif du refus et l'identité ainsi que la date de décision sont
conservés. Une commande soumise ne peut plus être modifiée directement.

Après approbation, les réceptions consignent la date, les quantités reçues,
endommagées ou manquantes et les observations. Le statut de livraison est
calculé à partir des quantités reçues et non endommagées ; les réceptions sont
conservées comme historique et ne sont pas modifiables depuis l'API. Une
évaluation fournisseur n'est possible que pour une commande entièrement
livrée, une fois par utilisateur et par commande.

Chaque nouveau paiement doit inclure une référence de règlement ; une même
référence ne peut pas être réutilisée pour la même facture.

## Structure

```text
backend/
  accounts/   utilisateurs, rôles, permissions et seed de démonstration
  audit/      journal d'audit et sauvegardes
  config/     paramètres Django, routes et configuration de tests
  invoices/   factures et lignes
  orders/     commandes d'achat, lignes et PDF
  payments/   paiements
  reports/    indicateurs et exports
  suppliers/  fournisseurs
frontend/
  src/        API, composants, contexte, routes, pages et styles React
```
