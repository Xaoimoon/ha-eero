# Documentation technique

Organisation du code, développement, suivi des projets amont et releases.

## Origine du code

- [schmittx/home-assistant-eero](https://github.com/schmittx/home-assistant-eero) : projet
  d'origine (MIT). Dernière version 1.8.1 (20/09/2025), 48 issues ouvertes, plus d'activité
  depuis.
- [lpleva/home-assistant-eero](https://github.com/lpleva/home-assistant-eero) : fork audité,
  pris à sa version 1.9.3 (19/09/2026). Il intègre les PR #169, #170, #171 et #174 de
  l'amont et corrige les 33 points d'un audit de code (détail dans `CHANGELOG.md`).
- Ce dépôt reprend l'historique Git complet des deux, puis continue à partir du tag `v1.9.3`.
  Les versions suivantes sont calculées par l'outillage de release (voir [Releases](#releases)).

Le domaine `eero`, les `unique_id` (`<network_id>-<key>` ou
`<network_id>-<resource_id>-<key>`) et le format de l'entrée de configuration restent ceux de
l'amont : une installation de la 1.8.1 passe sur cette intégration sans migration. Ne jamais
changer ces trois éléments sans prévoir de migration (`async_migrate_entry`, migration du
registre des entités).

## Organisation du code

- `api/` : client de l'API cloud eero (`https://api-user.e2ro.com/2.2/...`), synchrone, basé
  sur `requests` et appelé dans l'exécuteur de Home Assistant. `EeroAPI` gère la connexion
  (identifiant + code de vérification), le rafraîchissement de session (un seul par appel,
  sinon `EeroSessionExpired`), le 429 (`EeroRateLimited`, avec `Retry-After`) et les délais
  d'attente. Une classe par ressource (`network.py`, `eero.py`, `client.py`, `profile.py`,
  `backup_network.py`), toutes dérivées de `resource.py`.
- `__init__.py` : chargement de l'entrée, coordinateur (un relevé complet par intervalle),
  migration des entrées, `EeroEntity` (base de toutes les entités : `unique_id`,
  `device_info`, rattachement au réseau par `via_device_id`, indisponibilité quand la
  ressource disparaît de la réponse) et suppression des appareils.
- `device_removal.py` : règle de suppression des appareils depuis l'interface (clients
  déconnectés uniquement), sans dépendance à Home Assistant pour être testable seule.
- `config_flow.py` : connexion, vérification, réauthentification, choix des réseaux, des
  ressources, des mesures d'activité, options avancées.
- Plateformes : `binary_sensor`, `button`, `device_tracker`, `light`, `number`, `select`,
  `sensor`, `switch`, `time`, `update`. Les entités ne sont créées qu'au chargement de
  l'entrée : un client apparu ensuite attend le prochain rechargement.
- `services.yaml` : action `eero.set_blocked_apps` (eero Plus).

## Développement

Les scripts de `scripts/` suivent [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint).
Ils se lancent dans un environnement virtuel Python 3.14 (Linux, macOS ou WSL) :

```bash
scripts/setup     # installe Home Assistant (même version que la production)
scripts/test      # lance les tests
scripts/develop   # démarre un Home Assistant de test avec l'intégration, dans ./config
```

Home Assistant ne démarre pas nativement sous Windows : y lancer plutôt un conteneur, avec
l'intégration montée en direct (redémarrer le conteneur après une modification du code) :

```powershell
docker run -d --name ha-eero-dev -p 8123:8123 -e TZ=Europe/Paris `
  -v "${PWD}\config:/config" -v "${PWD}\custom_components:/config/custom_components" `
  ghcr.io/home-assistant/home-assistant:2026.9.4
```

Le dossier `config/` (gitignored) contient alors l'entrée de configuration et le jeton de
session du compte eero : ne jamais le committer. Les réponses brutes de l'API (option
« Save redacted server responses ») vont dans `config/.storage/eero_responses`. Les copier
dans `tests/fixtures/` seulement après avoir vérifié l'anonymisation (identifiants de réseau,
MAC, IP, noms d'appareils, SSID).

### Tests

```bash
scripts/test
```

Suite pytest sans Home Assistant : le paquet `api/` est chargé seul (`tests/helpers.py`) et
le réseau est simulé à partir des réponses de `tests/fixtures/`. Elle couvre l'analyse des
réponses, les erreurs et la session, l'enregistrement des réponses, la consommation de
données, les mises à jour de firmware, la suppression des appareils et la cohérence des
métadonnées du dépôt (`test_manifest.py`). Pas de tests du config flow ni des entités, qui
demanderaient `pytest-homeassistant-custom-component`.

## Suivi des projets amont

Les deux projets sont déclarés comme remotes du clone local :

```bash
git remote add upstream https://github.com/schmittx/home-assistant-eero.git
git remote add lpleva https://github.com/lpleva/home-assistant-eero.git
git fetch upstream && git fetch lpleva
git log --oneline v1.9.3..lpleva/main      # nouveautés du fork audité
git log --oneline v1.9.3..upstream/main    # nouveautés de l'amont
```

Reprendre une correction par `git cherry-pick -x <commit>` (la ligne « cherry picked from »
garde la trace de l'origine), puis reformuler le message au format Conventional Commits
(`git commit --amend`) pour qu'elle déclenche une release. Les PR ouvertes chez schmittx sont
aussi une source de correctifs : `git fetch upstream pull/<n>/head:pr-<n>`.

## Releases

Les versions sont calculées automatiquement à partir des messages de commit
([Conventional Commits](https://www.conventionalcommits.org/fr/)) par le workflow
`.forgejo/workflows/release.yml`, à chaque push sur `main` :

- `fix: …` ou `perf: …` → version corrective (2.0.**1**) ;
- `feat: …` → nouvelle fonctionnalité (2.**1**.0) ;
- `feat!: …` ou un pied de commit `BREAKING CHANGE:` → version majeure (**3**.0.0) ;
- les autres types (`docs`, `chore`, `refactor`, `test`, `ci`…) ne déclenchent pas de release.

`python scripts/bump_version.py --dry-run` affiche la prochaine version sans rien modifier.
Le workflow met à jour `manifest.json`, crée le tag et la release sur brokk. Les tags de
l'amont sans `v` (`1.8.1`…) sont ignorés ; le point de départ est le dernier tag `vX.Y.Z`.

`CHANGELOG.md` garde l'historique jusqu'à la 1.9.3. Les versions suivantes sont décrites
dans les notes de release, générées à partir des messages de commit.

### Releases GitHub et HACS

Le dépôt principal est sur [brokk](https://brokk.xaoimoon.fr/xaoimoon/ha-eero) ; GitHub en
est une copie (miroir push), utilisée par HACS. Le workflow `.github/workflows/release.yml`
transforme chaque tag reçu en release GitHub, que HACS propose comme mise à jour.
