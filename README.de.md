# Luftqualität Österreich

[![hacs][hacs-badge]][hacs]

Home-Assistant-Integration für Luftqualitätsmessdaten in Österreich (Datenquelle: Umweltbundesamt).

> **Inoffizielles Projekt.** Diese Integration wird unabhängig entwickelt und steht in keiner
> Verbindung zum Umweltbundesamt GmbH. Es besteht keine Gewähr für Verfügbarkeit, Aktualität
> oder Richtigkeit der Daten. Für rechtsverbindliche Auskünfte gilt ausschließlich die
> offizielle Veröffentlichung des Umweltbundesamts.

*English version: [README.md](README.md)*

## Status

**Funktionsfähig.** Messstationen werden über den Config Flow gefunden und eingerichtet, ihre
Sensoren werden alle 30 Minuten aktualisiert.

Die Daten stammen aus der JSON-Schnittstelle der öffentlichen Luftgütekarte auf
`luft.umweltbundesamt.at`. Diese Schnittstelle ist **nicht dokumentiert** und kann sich
jederzeit ändern oder wegfallen – die Integration liest sie so, wie es die Kartenanwendung
selbst tut. Gelesen werden zwei Mittelungszeiträume, der Halbstundenmittelwert (HMW) und der
Tagesmittelwert (TMW), macht 14 Abfragen pro Station und Aktualisierung; jeder Schadstoff und
Zeitraum wird einzeln und mit kurzer Pause dazwischen abgefragt, ein einzelner Fehlschlag legt
die Station nicht lahm.

Die Koordinierungsstelle Umweltinformation des Umweltbundesamts hat auf Anfrage bestätigt
(August 2026), dass dieser Endpunkt bei entsprechender Nennung der Datenquelle genutzt werden
darf, und das von der Integration verwendete Standardintervall von 30 Minuten empfohlen. Eine
andere dokumentierte Schnittstelle gibt es derzeit nicht; ein neues, dokumentiertes Service
wird erwogen.

Benötigt Home Assistant 2026.8.0 oder neuer. Keine zusätzlichen Python-Abhängigkeiten.

## Messgrößen

Jeder Schadstoff steht zweifach zur Verfügung: als aktueller Wert – der
Halbstundenmittelwert, der frischeste Wert der Datenquelle – und als Tagesmittelwert, auf den
sich die österreichischen Grenzwerte beziehen. Welche davon tatsächlich als Sensoren angelegt
werden, entscheidet die Auswahl beim Einrichten, siehe [Auswahl der
Entitäten](#auswahl-der-entitäten).

**Das Tagesmittel ist der Wert des abgeschlossenen Vortags**, kein laufendes Mittel des
aktuellen Tages. Es trifft kurz nach Mitternacht MEZ ein und bleibt dann bis zum nächsten
unverändert. Die Datenquelle rechnet ganzjährig in MEZ, im Sommer umfasst der Tag also
01:00 bis 01:00 Ortszeit.

| Schadstoff | Aktueller Wert | Tagesmittel (Vortag) | Einheit |
|---|---|---|---|
| Feinstaub PM10 | Feinstaub PM10 | Feinstaub PM10 Tagesmittel (Vortag) | µg/m³ |
| Feinstaub PM2.5 | Feinstaub PM2.5 | Feinstaub PM2.5 Tagesmittel (Vortag) | µg/m³ |
| Stickstoffdioxid NO₂ | Stickstoffdioxid | Stickstoffdioxid Tagesmittel (Vortag) | µg/m³ |
| Stickstoffmonoxid NO | Stickstoffmonoxid | Stickstoffmonoxid Tagesmittel (Vortag) | µg/m³ |
| Ozon O₃ | Ozon | Ozon Tagesmittel (Vortag) | µg/m³ |
| Schwefeldioxid SO₂ | Schwefeldioxid | Schwefeldioxid Tagesmittel (Vortag) | µg/m³ |
| Kohlenmonoxid CO | Kohlenmonoxid | Kohlenmonoxid Tagesmittel (Vortag) | mg/m³ |

Jeder Sensor trägt die passende Device Class und `state_class: measurement`, die Werte landen
also in der Langzeitstatistik. Die Entity-ID entsteht aus Stationsname und Sensorname in der
Sprache der Home-Assistant-Installation, zum Beispiel
`sensor.graz_don_bosco_feinstaub_pm10` und
`sensor.graz_don_bosco_feinstaub_pm10_tagesmittel_vortag`.

## Europäischer Luftqualitätsindex (EAQI)

Über die reinen Messwerte hinaus wird jede Station nach dem **European Air Quality Index**
der Europäischen Umweltagentur (EEA) eingestuft. Dafür kommen drei Arten von Entities dazu:

| Entity | Zustand | Inhalt |
|---|---|---|
| *Ozon Index*, *PM10 Index*, … | `good` … `extremely_poor` | Teilindex eines Schadstoffs |
| *Luftqualitätsindex* | `good` … `extremely_poor` | Stationsindex: der schlechteste Teilindex |
| *Luftqualitätsindex Stufe* | `1` … `6` | dasselbe als Zahl, für Graphen und Vergleiche |

Die Zustände sind englisch und stabil, damit Automationen unabhängig von der
Oberflächensprache funktionieren; übersetzt werden nur die Anzeigenamen.

### Bänder

Konzentrationen in µg/m³. Quelle: European Environment Agency, *European Air Quality
Index*, <https://airindex.eea.europa.eu/AQI/index.html>, Bändertabelle in der Fassung der
Revision 2024, abgerufen am 2026-08-31.

| Schadstoff | good | fair | moderate | poor | very poor | extremely poor |
|---|---|---|---|---|---|---|
| PM2.5 | 0–5 | 6–15 | 16–50 | 51–90 | 91–140 | > 140 |
| PM10 | 0–15 | 16–45 | 46–120 | 121–195 | 196–270 | > 270 |
| O₃ | 0–60 | 61–100 | 101–120 | 121–160 | 161–180 | > 180 |
| NO₂ | 0–10 | 11–25 | 26–60 | 61–100 | 101–150 | > 150 |
| SO₂ | 0–20 | 21–40 | 41–125 | 126–190 | 191–275 | > 275 |

Ein Wert exakt auf einer Bandgrenze gehört zur unteren Stufe: 5 µg/m³ PM2.5 sind noch
`good`.

**Kohlenmonoxid und Stickstoffmonoxid sind nicht Teil des EAQI.** Sie bekommen keinen
Teilindex und tragen nichts zum Stationsindex bei; ihre Messsensoren bleiben unverändert.

### Der Stationsindex und seine zwei Regeln

Der Stationsindex ist der schlechteste der Teilindizes – aber nur, wenn eine der beiden
Mindestdatenregeln der EEA erfüllt ist:

| Regel | braucht | `index_basis` | `index_complete` |
|---|---|---|---|
| Standard (Hintergrund- und Industriestationen) | NO₂, O₃ **und** Feinstaub | `standard` | `true` |
| Verkehrsstationen | NO₂ **und** Feinstaub | `traffic_rule` | `false` |

Feinstaub heißt PM2.5 oder PM10 oder beide. Ohne NO₂ oder ohne Feinstaub greift keine der
beiden Regeln: Diese Stationen bekommen keinen Stationsindex, der Wert bleibt `unknown`. Er
fällt **nicht** auf den besten verfügbaren Teilindex zurück, denn das würde die Lage
beschönigen. Eine Station, die nur Ozon liefert, zeigt daher einen Ozon-Teilindex und einen
unbekannten Stationsindex.

**Eine Station ohne Ozon wird an der Verkehrsstationsregel gemessen.** Die Datenquelle
veröffentlicht den Stationstyp nicht – eine Verkehrsstation ist von einer Hintergrundstation,
die schlicht kein Ozon misst, nicht zu unterscheiden. Beide nach der milderen Regel zu
bewerten ist eine bewusste Abwägung: Die vielen Stationen ohne Ozonmessung bekommen dadurch
überhaupt einen Index, und an einer Hintergrundstation kann er im Sommer zu optimistisch
ausfallen, weil Ozon dort oft der Schadstoff wäre, der die Stufe bestimmt hätte. Lies
`index_basis`, bevor du dich auf eine Stufe verlässt, und vergleiche Stufen nur innerhalb
derselben Basis – `traffic_rule` und `standard` sind nicht dieselbe Skala.

Erfüllt eine Station keine der beiden Regeln, ist der Stationsindex beim Einrichten nicht
vorausgewählt – zwei Entitäten, die nie aus `unknown` herauskommen, sind weniger wert als ihr
Fehlen. Anhaken lässt er sich im Formular trotzdem, und ein Eintrag, der die Entität schon
hat, behält sie.

### Mittelungszeitraum – eine Näherung

**Der EAQI ist auf Stundenmittelwerten definiert. Diese Integration verwendet
Halbstundenmittelwerte (HMW)**, den frischesten Wert der Datenquelle. Der Index ist damit
eine Näherung und kann vom offiziellen Wert abweichen – am ehesten bei kurzen Spitzen, die
ein Stundenmittel stärker glättet als ein Halbstundenmittel.

Jeder Index-Sensor weist das im Attribut `averaging_basis` aus. Tagesmittelwerte (TMW)
werden für den Index bewusst nicht herangezogen – sie beschreiben den Vortag, nicht die
Gegenwart.

### Attribute

Der Stationsindex und sein numerisches Gegenstück tragen:

| Attribut | Bedeutung |
|---|---|
| `dominant_pollutant` | welcher Schadstoff die Stufe bestimmt |
| `pollutants_used` | die eingeflossenen Schadstoffe |
| `index_basis` | nach welcher Regel die Stufe gebildet wurde: `standard` oder `traffic_rule` |
| `index_complete` | ob alle drei Gruppen der Standardregel vorlagen |
| `averaging_basis` | der tatsächlich verwendete Mittelungszeitraum |
| `scheme` | Indexschema samt Revision |

Die Teilindex-Sensoren tragen `averaging_basis` und `scheme`.

> **Der Index ist kein Werkzeug zur Grenzwertprüfung.** Die EEA stellt ausdrücklich fest,
> dass der Luftqualitätsindex kein Werkzeug zur Prüfung der Einhaltung von
> Luftqualitätsgrenzwerten ist und dafür nicht verwendet werden darf. Für rechtsverbindliche
> Grenzwerte gilt die offizielle Veröffentlichung des Umweltbundesamts.

## Automationen

Die Schadstoffsensoren tragen die üblichen Device Classes, deshalb funktionieren die Trigger
und Bedingungen der Home-Assistant-Building-Block-Integration
[Air Quality](https://www.home-assistant.io/integrations/air_quality/) direkt mit ihnen –
ohne Hilfsentities. Schwellenwerte sind Geschmackssache und hängen vom Anlass ab, deshalb
bringt diese Integration bewusst keine eigenen mit.

### Blueprint: Benachrichtigung bei Schwellenwert-Überschreitung

Für den häufigsten Fall – *sag mir Bescheid, wenn ein Wert über X steigt* – liegt eine
fertige Automatisierung im Repository. Ein Klick importiert sie in die eigene Installation:

[![Diese Home-Assistant-Instanz öffnen und den Blueprint-Import-Dialog anzeigen.][my-blueprint-badge]][my-blueprint]

| Eingabe | Wofür sie da ist |
|---|---|
| **Sensor** | Der überwachte Messwert. Zur Auswahl stehen nur die numerischen Sensoren dieser Integration; für den Index selbst ist es *Luftqualitätsindex Stufe* (1 bis 6). |
| **Schwellenwert** | Der Wert, über den der Sensor steigen muss, in der Einheit des Sensors. Bewusst nicht vorbelegt – siehe unten. |
| **Benachrichtigung** | Was bei einer Überschreitung passiert. Vorbelegt mit einer dauerhaften Benachrichtigung; ersetzbar durch den eigenen Benachrichtigungsdienst. Darin stehen die Variablen `sensor_name`, `value`, `unit`, `threshold`, `station` und `measured_at` zur Verfügung. |
| **Mindestabstand zwischen zwei Meldungen** | Voreingestellt eine Stunde. Ein Wert, der um den Schwellenwert schwankt, überschreitet ihn immer wieder; in dieser Zeit werden weitere Überschreitungen ignoriert, damit aus einer Überschreitung eine Meldung wird. |

> **Es ist kein Schwellenwert vorbelegt, und das mit Absicht.** Die österreichischen
> Grenzwerte, Informations- und Alarmschwellen stehen im IG-L und im Ozongesetz, und jede
> einzelne bezieht sich auf einen bestimmten Mittelungszeitraum. Der Blueprint kann nicht
> prüfen, ob der gewählte Sensor zum Mittelungszeitraum des jeweiligen Werts passt, und ein
> amtlich aussehender Schwellenwert auf dem falschen Mittelwert ist schlechter als gar keine
> Warnung. Die Zahl im Gesetzestext nachsehen ([RIS](https://www.ris.bka.gv.at)) und den
> Sensor mit dem passenden Mittelungszeitraum wählen.

Die Wartezeit ist eine Verzögerung am Ende der Automatisierung, die im Modus `single`
läuft: Während sie wartet, treffen weitere Überschreitungen auf einen laufenden Durchgang
und werden still verworfen. Ein Neuladen der Automationen oder ein Neustart von Home
Assistant beendet diese Wartezeit vorzeitig.

Die Datei ist `blueprints/automation/austrian_air_quality/schwellenwert_benachrichtigung.yaml`;
[eine englische Fassung](blueprints/automation/austrian_air_quality/threshold_notification.yaml)
derselben Automatisierung liegt daneben.

### Von Hand geschrieben

Ozon-Informationsschwelle, 180 µg/m³:

```yaml
automation:
  - alias: Ozon-Informationsschwelle erreicht
    triggers:
      - trigger: air_quality.ozone_crossed_threshold
        target:
          entity_id: sensor.graz_sud_tiergartenweg_ozon
        options:
          behavior: each
          threshold:
            type: above
            value:
              number: 180
              unit_of_measurement: "μg/m³"
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            Ozon über der Informationsschwelle von 180 µg/m³:
            {{ states('sensor.graz_sud_tiergartenweg_ozon') }} µg/m³
```

> Die österreichische Informationsschwelle von 180 µg/m³ ist gesetzlich als
> **Einstundenmittelwert** (MW1) definiert. Der Sensor oben ist ein Halbstundenmittelwert,
> die Automation ist also eine Näherung und schlägt etwas früher und etwas öfter an als die
> offizielle Bewertung. Sie ist ein Anlass, in die offiziellen Werte zu sehen, kein Ersatz
> dafür.

PM10 als Bedingung – der österreichische Grenzwert von 50 µg/m³ bezieht sich auf den
Tagesmittelwert, deshalb ist hier der Tagesmittel-Sensor der richtige. Zu bedenken: Der
Sensor meldet **gestern**, die Automatisierung liest sich also als „gestern war es sauber"
und nicht als „die Luft ist gerade sauber":

```yaml
automation:
  - alias: Nur lüften, wenn PM10 niedrig ist
    triggers:
      - trigger: state
        entity_id: binary_sensor.wohnzimmer_fenster
        to: "on"
    conditions:
      - condition: air_quality.is_pm10_value
        target:
          entity_id: sensor.graz_don_bosco_feinstaub_pm10_tagesmittel_vortag
        options:
          behavior: any
          threshold:
            type: below
            value:
              number: 50
    actions:
      - action: notify.persistent_notification
        data:
          message: PM10-Tagesmittel von gestern unter 50 µg/m³ – guter Zeitpunkt zum Lüften.
```

Die Entity-IDs sind durch die eigenen zu ersetzen; sie entstehen aus dem Stationsnamen in
der Sprache der eigenen Installation.

Die Index-Entities lassen sich in gewöhnlichen Zustandstriggern verwenden, weil ihre
Zustände stabil sind:

```yaml
automation:
  - alias: Warnen, wenn die Luftqualität schlecht wird
    triggers:
      - trigger: state
        entity_id: sensor.graz_sud_tiergartenweg_luftqualitatsindex
        to:
          - poor
          - very_poor
          - extremely_poor
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            Luftqualität ist
            {{ states('sensor.graz_sud_tiergartenweg_luftqualitatsindex') }},
            bestimmt durch
            {{ state_attr('sensor.graz_sud_tiergartenweg_luftqualitatsindex',
                          'dominant_pollutant') }}.
```

## Installation

### HACS (benutzerdefiniertes Repository)

Die Integration ist (noch) nicht Teil des HACS-Standardkatalogs, das Repository muss daher
einmalig von Hand hinzugefügt werden. Ein Klick erledigt das und öffnet direkt die
Downloadseite:

[![Diese Home-Assistant-Instanz öffnen und das Repository im Home Assistant Community Store anzeigen.][my-badge]][my-hacs]

Oder manuell:

1. HACS öffnen → Integrationen → Menü (⋮) → *Benutzerdefinierte Repositories*
2. `https://github.com/karlrt/ha-austrian-air-quality` als Kategorie *Integration* hinzufügen
3. „Luftqualität Österreich" installieren, Home Assistant neu starten
4. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Luftqualität Österreich*

HACS bietet ausschließlich getaggte Releases an, nicht den Stand des Standardbranches.

### Manuell

Den Ordner `custom_components/austrian_air_quality` in das `config/custom_components/`
Verzeichnis der Home-Assistant-Installation kopieren und neu starten.

## Konfiguration

Die Einrichtung erfolgt vollständig über die Benutzeroberfläche (Config Flow). Pro
Messstation wird ein Eintrag angelegt. Die Messstelle kann auf zwei Wegen gesucht werden:

- **Auf der Karte (Umkreis)** – den Marker auf den eigenen Standort setzen und den Kreis auf
  den gewünschten Suchradius ziehen (Standard 15 km, maximal 100 km). Alle Messstellen im
  Kreis werden nach Entfernung sortiert aufgelistet, die nächstgelegene zuerst.
- **Nach Stationsname** – einen Teil des Namens oder der Adresse eingeben, z. B. `Graz` oder
  `Stephansplatz`.

Die Trefferliste zeigt bereits, welche Werte jede Station liefert. Nach der Auswahl folgt eine
Detailansicht mit Adresse, Betreiber, Entfernung und den aktuellen Messwerten aller
Schadstoffe, bevor der Eintrag angelegt wird. Bereits eingerichtete Messstellen werden
ausgeblendet. Liefert eine Suche mehr als 25 Stationen, wird statt der Liste ein genauerer
Suchbegriff verlangt.

Die Benutzeroberfläche gibt es auf Deutsch und Englisch.

### Auswahl der Entitäten

Nach der Detailansicht folgt die Auswahl der Messwerte. Angeboten wird immer der vollständige
Katalog – sieben Schadstoffe mal zwei Mittelwerttypen –, vorausgewählt ist, was die Station
gerade meldet. Der Unterschied ist wichtig: Ein Schadstoff, den die Station im Moment des
Einrichtens gerade aussetzt, lässt sich trotzdem anhaken und liefert Werte, sobald er wieder
da ist.

Der Schalter *Die übrigen Entitäten mit auswählen* öffnet einen zweiten Schritt mit den
EAQI-Teilindizes, dem Stationsindex und der Koordinaten-Entität. Ohne Haken werden sie
passend zur Messwertauswahl angelegt.

Nachträglich ändern lässt sich alles über *Konfigurieren* am Eintrag; dort steht der volle
Umfang in einem Formular. Der Eintrag wird danach automatisch neu geladen.

**Was die Auswahl kostet.** Jeder angehakte Messwert ist eine Abfrage pro
Aktualisierungszyklus, also alle 30 Minuten. Der Vollausbau sind 14 Abfragen pro Station,
eine Auswahl aus zwei Werten sind zwei.

**Wann abgefragt wird.** Die Quelle veröffentlicht auf einem festen Halbstundenraster, und
jeder Eintrag fragt einmal pro veröffentlichtem Wert ab – an einer festen Position innerhalb
des Halbstundenfensters. Die Position wird aus der ID des Eintrags abgeleitet: Sie bleibt über
Neustarts hinweg gleich, unterscheidet sich aber zwischen den Stationen einer Installation und
zwischen Installationen. Damit wandert der Abruf nicht langsam am Raster vorbei (und
überspringt gelegentlich einen Halbstundenwert), und die Abfragen aller Installationen treffen
nicht auf dieselbe Sekunde.

**Der Start wartet nicht auf Messwerte.** Der Entitätsbestand kommt aus der Auswahl, der erste
Abruf läuft daher im Hintergrund neben dem restlichen Start. Bis er ankommt, stehen die
Sensoren auf *nicht verfügbar* – vorher hielt jeder Eintrag den Start von Home Assistant um
die Dauer eines vollständigen Abrufs auf, rund eine halbe Minute pro Station.

**Abgewählte Entitäten werden nicht gelöscht.** Sie werden nur nicht mehr angelegt und stehen
in Home Assistant als *nicht verfügbar*. Registry-Eintrag und Langzeitstatistik bleiben
erhalten, beim Wiederanhaken kommen sie mit derselben Entity-ID und ihrer Historie zurück.
Wer sie wirklich loswerden will, löscht sie in Home Assistant selbst – dann ist auch die
Historie weg.

**Der Stationsindex braucht mehr als seine eigene Entität.** Er wird mindestens aus NO₂ und
Feinstaub gebildet, und zusätzlich aus Ozon, wo die Station es meldet. Solange er ausgewählt
ist, werden die dafür nötigen Werte abgefragt, auch wenn die zugehörigen Messwert-Sensoren
abgewählt sind. Ein abgewählter Messwert kostet also seine Entität, aber nie stillschweigend den Index.
Dasselbe gilt für die Teilindizes.

**Der Entitätsbestand hängt nur an der Auswahl** – nicht daran, was die Station im Moment des
Einrichtens oder eines Neustarts gerade gemeldet hat. Eine Messlücke lässt einen Sensor
vorübergehend auf *nicht verfügbar* stehen und danach von selbst weiterlaufen; zuvor
verschwand er in diesem Fall dauerhaft und kam erst nach einem Neuladen des Eintrags zurück.

Bestehende Einträge bekommen beim Update automatisch eine Auswahl: alles, was sie schon
haben, plus alles, was ihre Station beim ersten Abruf danach meldet. Es geht also nichts
verloren, und ein Sensor, der wegen einer solchen Messlücke fehlte, kommt zurück.

## Station auf der Karte

Jede Station bekommt zusätzlich eine Diagnose-Entität **Koordinaten** – sofern in der
Auswahl aktiviert –, deren Zustand die Position als `47.06695, 15.44226` anzeigt. Sie steht auf der Geräteseite unter *Diagnose* und
ist der passende Eintrag für eine Karten-Karte, weil es sie genau einmal pro Station gibt.

Jeder Sensor – auch die Koordinaten-Entität – liefert die Stationsdaten als Attribute mit:

| Attribut | Bedeutung |
|---|---|
| `latitude`, `longitude` | Koordinaten der Messstelle |
| `location` | Adresse laut Umweltbundesamt |
| `owner` | Betreiber der Messstelle |
| `station_id` | Kennung der Messstelle |
| `altitude` | Seehöhe der Messstelle in Metern |
| `measured_at` | Zeitpunkt der Messung (ISO 8601, nur bei Schadstoffsensoren) |
| `value_class` | Belastungsklasse des Werts – die Farbskala der offiziellen Karte – nur vorhanden, wenn die Quelle eine vergibt |

Weil `latitude` und `longitude` vorhanden sind, kann die Messstelle direkt in einer
Karten-Karte angezeigt werden:

```yaml
type: map
entities:
  - sensor.graz_don_bosco_koordinaten
```

Alle Sensoren einer Station tragen dieselben Koordinaten – für die Karte genügt daher
ein Sensor pro Station, sonst liegen mehrere Marker exakt übereinander.

## Dashboard

Eine fertige Ansicht mit den aktuellen Messwerten, der Station auf der Karte und den
letzten 24 Stunden. Unter *Dashboard bearbeiten → ⋮ → Raw-Konfigurationseditor* den Block
unter `views:` einfügen und die Entity-IDs durch die eigenen ersetzen:

```yaml
- title: Luftqualität
  path: luftqualitaet
  icon: mdi:air-filter
  type: sections
  max_columns: 2
  sections:
    - type: grid
      cards:
        - type: heading
          heading: Graz Don Bosco
        - type: entities
          title: Aktuelle Messwerte
          state_color: true
          entities:
            - entity: sensor.graz_don_bosco_luftqualitatsindex
            - entity: sensor.graz_don_bosco_feinstaub_pm10
            - entity: sensor.graz_don_bosco_feinstaub_pm2_5
            - entity: sensor.graz_don_bosco_stickstoffdioxid
            - entity: sensor.graz_don_bosco_ozon
            - type: attribute
              entity: sensor.graz_don_bosco_feinstaub_pm10
              attribute: measured_at
              name: Messung von
    - type: grid
      cards:
        - type: heading
          heading: Messstelle
        - type: map
          entities:
            - sensor.graz_don_bosco_koordinaten
          theme_mode: auto
          auto_fit: true
    - type: grid
      cards:
        - type: heading
          heading: Letzte 24 Stunden
        - type: history-graph
          hours_to_show: 24
          entities:
            - entity: sensor.graz_don_bosco_feinstaub_pm10
            - entity: sensor.graz_don_bosco_stickstoffdioxid
            - entity: sensor.graz_don_bosco_ozon
```

Zu den drei Karten:

- **Aktuelle Messwerte** – die Halbstundenmittelwerte, als letzte Zeile das Attribut
  `measured_at`: Es sagt, wie alt die Zahlen auf der Karte sind. Die Tagesmittel-Sensoren
  passen ebenfalls hierher, solange klar bleibt, dass sie den [Vortag](#messgrößen) melden.
- **Messstelle** – die Karte braucht genau eine Entität pro Station, sonst liegen mehrere
  Marker übereinander; siehe [Station auf der Karte](#station-auf-der-karte).
- **Letzte 24 Stunden** – der Verlauf zeigt nur, was der Recorder aufgehoben hat. Direkt
  nach dem Einrichten ist die Karte leer und füllt sich im Lauf des Tages.

Es gibt nur die Entitäten, die in der Auswahl aktiviert wurden; die übrigen Zeilen
entweder löschen oder die Entitäten unter *Konfigurieren* nachziehen.

## Entwicklung

- Domain: `austrian_air_quality` (unveränderlich nach dem ersten Release)
- Anzeigename: `Luftqualität Österreich`
- Repository: `ha-austrian-air-quality`
- Jeder Push wird von hassfest und der HACS-Action geprüft (siehe `.github/workflows/validate.yml`)
- Vor einem Release `version` in der `manifest.json` erhöhen; `.github/workflows/release.yml`
  lässt das Release fehlschlagen, wenn Tag und Manifest-Version auseinanderlaufen

`eaqi.py` enthält die Indexklassifikation und importiert bewusst nichts aus Home Assistant.
Die Unit-Tests laufen deshalb mit einem nackten Python ohne Zusatzpakete:

```bash
python -m unittest discover -s tests -v
```

Die zwei Dateien unter `blueprints/automation/austrian_air_quality/` sind dieselbe
Automatisierung in zwei Sprachen; unterscheiden dürfen sich nur die Beschriftungen.
`tests/test_blueprints.py` vergleicht sie und schlägt fehl, wenn sie auseinanderlaufen –
es ist der einzige Test, der PyYAML braucht, und überspringt sich ohne das Paket selbst.

Siehe `custom_components/austrian_air_quality/` für den Quellcode.

## Lizenz

Apache-2.0 – siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=karlrt&repository=ha-austrian-air-quality&category=integration
[my-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[my-blueprint]: https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkarlrt%2Fha-austrian-air-quality%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Faustrian_air_quality%2Fschwellenwert_benachrichtigung.yaml
[my-blueprint-badge]: https://my.home-assistant.io/badges/blueprint_import.svg
