# Remotion-проект
1. `python3 ../tools/build_timeline.py` — пересобрать timing.json / SRT / голосовую дорожку из реплик
2. `npm i` → `npm run dev` — студия на :3000
3. `npm run render` → `../release/final.mp4`
Сцены: `src/scenes/S<блок>_<номер>.tsx`, регистрируются в `src/scenes/index.tsx`. Границы сцен вычисляются из таймкодов озвучки автоматически.
