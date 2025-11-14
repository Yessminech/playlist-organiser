pip3 install python-dotenv

Harmonics mixer
python3 camelot_mixer_harmonics_first.py --input gpt_extraction/funky_haus_66_complete.json

BPM Mixer
python3 camelot_mixer_bpm_first.py --input gpt_extraction/funky_haus_66_complete.json

New playlist
python3 spotify_upload_playlist.py --input final_mix.json --name "Funky Haus DJ Mix"

Existing playlist
python3 spotify_upload_playlist.py --input final_mix.json --playlist-id 5Kf3Lh23me2XYZ8
