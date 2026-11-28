# Asset credits

Every post's description ends with a "Visuals:" line that credits ONLY the assets the video actually uses. Join the parts that apply with "; ".

| Asset used in the video | Credit text to include |
|---|---|
| Planet, Moon, Sun or Milky Way maps (kit.earth / moon / planet / sun_sphere / world) | planet textures by Solar System Scope (CC BY 4.0) from NASA data |
| NASA spacecraft models (kit.nasa_model / hubble) | spacecraft models from NASA 3D Resources |
| Human anatomy (kit.anatomy) | anatomy models from BodyParts3D, © The Database Center for Life Science (CC BY-SA 2.1 JP) |
| US state outlines (us-atlas npm package, used by the ys_anim.py maps) | US state outlines from us-atlas (ISC) / US Census Bureau |
| Any other downloaded model or dataset | "<asset name> by <author> (<license>)" |

Example: `Visuals: planet textures by Solar System Scope (CC BY 4.0) from NASA data; spacecraft models from NASA 3D Resources.`
If the video uses none of these (all built in-house), leave the line out.

Notes:
- Solar System Scope textures: CC BY 4.0, built from NASA mission data. Attribution is required.
- Earth normal and specular maps: three.js example textures (MIT).
- NASA 3D Resources: free to use under NASA media guidelines. They must not imply NASA endorsement.
- BodyParts3D (via github.com/Kevin-Mattheus-Moerman/BodyParts3D): CC BY-SA 2.1 Japan. Attribution is required.
- us-atlas 3.0.1 (npm, ISC license, by Mike Bostock): TopoJSON of US Census Bureau cartographic boundary files (public domain). Install with `npm pack us-atlas@3.0.1` into /home/claude/geo and untar.
- Sky, ocean, terrain, clouds and materials are generated in Blender (no credit needed).
