# eero pour Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/Xaoimoon/ha-eero?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/releases)
[![Licence](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/blob/main/LICENSE)

[![Maintenu](https://img.shields.io/badge/maintained-yes-green.svg?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/commits/main)
[![Activité](https://img.shields.io/github/commit-activity/y/Xaoimoon/ha-eero?style=for-the-badge)](https://github.com/Xaoimoon/ha-eero/commits/main)

Intégration Home Assistant (non officielle) pour les réseaux Wi-Fi maillés eero. Elle passe par le compte eero (API cloud, comme l'application mobile) pour afficher et piloter le réseau, les eero, les profils et les appareils connectés.

C'est la suite maintenue de [schmittx/home-assistant-eero](https://github.com/schmittx/home-assistant-eero), sans nouvelle version depuis la 1.8.1 (septembre 2025), reprise à partir du fork audité [lpleva/home-assistant-eero](https://github.com/lpleva/home-assistant-eero) 1.9.3. Le domaine reste `eero` : une installation existante se met à jour sans rien reconfigurer (voir [Venir de l'intégration de schmittx](#venir-de-lintégration-de-schmittx)).

## Fonctionnalités

- Plusieurs réseaux par compte.
- Réglages du réseau : réseau invité, fonctions eero Plus et eero Labs.
- Pause de l'accès à Internet par profil ou par appareil, filtres de contenu des profils, applications bloquées (eero Plus).
- Présence des appareils et des profils, avec la bande, le canal et la largeur de canal des appareils Wi-Fi.
- Capteurs de signal, de débit, de consommation de données et d'activité (eero Plus).
- Boutons pour les actions qui redémarrent le réseau, mises à jour du firmware des eero.
- Veilleuse des eero Beacon (mode, horaires, luminosité).
- Réseaux de secours (eero Plus).

## Installation

### Via HACS (recommandé)

[![Ouvrir le dépôt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Xaoimoon&repository=ha-eero&category=integration)

Cliquer sur le bouton ci-dessus, ou ajouter le dépôt à la main :

1. Dans HACS, menu **⋮ > Dépôts personnalisés**, ajouter `https://github.com/Xaoimoon/ha-eero` avec le type **Intégration**.
2. Rechercher "eero" dans HACS, puis **Télécharger**.
3. Redémarrer Home Assistant.

HACS vous proposera ensuite automatiquement les nouvelles versions.

### Manuelle

1. Repérer le dossier de configuration de Home Assistant (celui qui contient `configuration.yaml`).
2. Y créer un dossier `custom_components` s'il n'existe pas déjà.
3. Copier le dossier `custom_components/eero` de ce dépôt dedans, pour obtenir `<config>/custom_components/eero/`.
4. Redémarrer Home Assistant.

## Configuration

[![Ajouter l'intégration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=eero)

Cliquer sur le bouton ci-dessus, ou :

1. **Paramètres > Appareils et services > Ajouter une intégration**, chercher "eero".
2. Saisir l'adresse e-mail ou le numéro de téléphone du compte eero, puis le code de vérification reçu.
3. Choisir les réseaux, puis les ressources à suivre (eero, profils, appareils filaires et Wi-Fi, réseaux de secours) et les mesures d'activité.

Ces choix se modifient ensuite dans les **options** de l'intégration, de même que l'intervalle de relevé (5 minutes par défaut, 1 minute au minimum) et le délai d'attente.

Home Assistant Core 2026.8 ou plus récent est requis.

## Bon à savoir

- **Langue** : la configuration, les options, l'action et les états sont traduits en français. Les noms des entités restent pour l'instant en anglais.
- **Compte Amazon** : la connexion par un compte Amazon n'est pas prise en charge. Créer un compte eero classique et l'ajouter comme administrateur du réseau ([marche à suivre](https://github.com/schmittx/home-assistant-eero/issues/77#issuecomment-1960875926)).
- **Session expirée** : si eero invalide la session, Home Assistant propose de se réauthentifier avec un nouveau code de vérification, sans supprimer l'intégration.
- **Appareils disparus** : un appareil qu'eero ne signale plus passe en « indisponible ». Il peut être supprimé depuis sa fiche dans Home Assistant et il est recréé s'il revient. Le réseau, les eero et les profils ne peuvent pas être supprimés de cette façon.
- **Ménage automatique** : l'option « Supprimer les appareils clients absents depuis » (options diverses, réglée par réseau, 0 = jamais) supprime les appareils filaires et Wi-Fi qui ne se sont pas connectés depuis ce nombre de jours, avec leurs entités. C'est utile quand un appareil change d'adresse MAC à chaque connexion (certaines voitures, téléphones en adresse aléatoire) et laisse un nouvel appareil derrière lui à chaque fois. Un appareil que vous avez renommé, rangé dans une pièce, étiqueté, ou dont une entité porte un nom, une icône ou une étiquette à vous, n'est jamais supprimé. La date retenue est la plus récente entre la dernière activité donnée par eero et la dernière connexion vue par l'intégration ; un appareil qu'eero ne signale plus est compté à partir de la première fois que l'intégration le rencontre sans date.
- **Action `eero.remove_stale_devices`** : même ménage à la demande. Par défaut c'est une simulation (`dry_run: true`) qui renvoie la liste des appareils concernés, à lancer depuis **Outils de développement > Actions** avec « Renvoyer la réponse » :

  ```yaml
  action: eero.remove_stale_devices
  data:
    days: 7
    dry_run: true          # false pour supprimer vraiment
    remove_unknown: false  # true : inclure les appareils sans date connue
  ```

  `remove_unknown: true` sert au premier ménage : il inclut, quel que soit le délai, les appareils qu'eero ne signale plus et que l'intégration n'a jamais vus connectés (le stock accumulé avant l'activation de la fonction). Toujours le lancer d'abord en simulation.
- **Nouveaux appareils** : seuls les appareils présents au chargement de l'intégration reçoivent des entités. Un appareil apparu depuis n'est ajouté qu'au prochain rechargement.

## Venir de l'intégration de schmittx

L'intégration garde le domaine `eero`, les identifiants uniques des entités et le format de l'entrée de configuration. Les appareils, les entités, et les noms et icônes personnalisés sont conservés.

1. Dans HACS, ouvrir l'intégration eero actuelle, menu **⋮ > Supprimer**. Cela retire ses fichiers, pas l'entrée de configuration.
2. Ajouter ce dépôt et le télécharger (voir [Installation](#via-hacs-recommandé)), **avant** de redémarrer.
3. Redémarrer Home Assistant.

Changements visibles par rapport à la 1.8.1 :

- les deux entités image de QR code (réseau et réseau invité) disparaissent et peuvent être supprimées ;
- les noms d'entités suivent la convention de Home Assistant (nom de l'appareil + nom de la mesure) : les noms affichés peuvent changer, mais pas les identifiants des entités déjà créées ;
- l'interrupteur `secondary_wan_deny_access` devient `secondary_wan_allow_access`, de sens inverse ;
- l'intervalle de relevé est désormais d'au moins 1 minute, et de 5 minutes par défaut ;
- en cas d'erreur de l'API, les entités passent en « indisponible » au lieu de garder leur dernière valeur.

Le détail est dans [CHANGELOG.md](https://github.com/Xaoimoon/ha-eero/blob/main/CHANGELOG.md).

## Avertissement

Projet non affilié à eero ni à Amazon. L'intégration repose sur l'API cloud non documentée de l'application eero, qui peut changer sans préavis.

## Remerciements

- [@schmittx](https://github.com/schmittx/home-assistant-eero) : l'intégration d'origine ;
- [@lpleva](https://github.com/lpleva/home-assistant-eero) : l'audit et les corrections de la 1.9 ;
- [@343max](https://github.com/343max/eero-client) : l'authentification de l'API ;
- [@jrlucier](https://github.com/jrlucier/eero_tracker) : l'idée de départ.

## Licence

MIT — voir [LICENSE](https://github.com/Xaoimoon/ha-eero/blob/main/LICENSE).
