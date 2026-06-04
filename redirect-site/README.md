# redirect-site

A static redirect that lives alongside the tracker app in this repo. It permanently
redirects the old Render URL `chenesai.onrender.com` to the Pi-hosted tracker at
`https://simukira.duckdns.org`, preserving path + query.

This folder is **not** used by the Docker/Flask app or the Pi — it exists only so Render
can deploy it as a **Static Site** from the same repo.

## Deploy on Render (dashboard)

1. **Delete** the old (suspended) `chenesai` web service — Settings → Delete Service. This
   removes the old build/image and frees the `chenesai.onrender.com` name.
2. **New → Static Site**, connect this repo (`simbadzina/tracker`).
3. Settings:
   - **Name:** `chenesai` (to reclaim `chenesai.onrender.com`)
   - **Build Command:** *(leave empty)*
   - **Publish Directory:** `redirect-site`
4. Create. `chenesai.onrender.com/anything` then 301s to `simukira.duckdns.org/anything`.

A 301 is a few hundred bytes, so this stays comfortably inside Render's free static-site
bandwidth.
