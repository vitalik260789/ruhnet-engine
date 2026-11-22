# ruhnet-engine

Физические Shorts «РУХНЕТ?»: башня из предметов, предметы вытаскиваются по одному, момент обрушения считает физика (pymunk), картинку рендерит Blender (Cycles) поверх фотографии.

## Как устроено
1. `tools/plan3d.py` — физика выбирает ходы и проигрывает их по таймлайну ролика → `out/frames.json` (положение всех предметов в каждом кадре, уникальные кадры).
2. `tools/render3d.py --shard k/N` — Blender рендерит свою долю уникальных кадров: только предметы и тень (прозрачный фон).
3. `tools/compose.py` — фото + 3D-слой + надписи, счётчик, подсветка, наезд камеры → `silent.mp4`.
4. `tools/sound3d.py` — звук из событий физики (стекло, доски, волны).
5. `.github/workflows/render3d.yml` — всё это на 20 машинах GitHub Actions, в конце GitHub Release с mp4.

## Материалы
`config.json` → `"material"`: `bottles` (бутылки с досками), `cans` (банки с досками), `blocks` (деревянные бруски вперевязку), `ice` (ледяные кирпичики).
Фон: `"bg_url"` (фото скачивается в Actions) или `"bg"` (файл в папке проекта); `bg_horizon`/`bg_cx` — горизонт и центр кадра в пикселях фото шириной `bg_ref_width`; `horizon_y` — где горизонт в кадре.
`platform: [ширина, глубина]` — деревянный настил под башней (для травы/воды). Фото со стоков смотрим через `fetch.json` → workflow `fetch`.

## Новый ролик
Скопировать `projects/bottles_beach` → `projects/<slug>`, поменять `config.json` (seed, фон, подписи) и фото,
в `render.json` написать `"project": "<slug>"`, закоммитить — рендер стартует сам.

Проверка до рендера (локально): `python3 tools/plan3d.py projects/<slug>` →
`python3 tools/render3d.py projects/<slug> --pct 50 --spp 12 --only <ids>` → `python3 tools/compose.py projects/<slug> --stills <frames>`.

Шрифты Inter — SIL Open Font License. Фон `projects/bottles_beach/bg.jpg` — фото с Pexels.
