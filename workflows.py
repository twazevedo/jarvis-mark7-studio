"""Workflows do ComfyUI (formato API) gerados dinamicamente."""
import random


def _seed():
    return random.randint(0, 2**32 - 1)


def image_workflow(prompt: str, c: dict) -> dict:
    """Texto -> imagem usando qualquer checkpoint SD 1.5 / SDXL."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": c["checkpoint"]}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": c["negative"], "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": c["width"], "height": c["height"], "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": _seed(), "steps": c["steps"], "cfg": c["cfg"],
            "sampler_name": c["sampler"], "scheduler": c["scheduler"],
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "jarvis_img"}},
    }


def video_workflow(prompt: str, c: dict) -> dict:
    """Texto -> video com Wan 2.1 T2V 1.3B (nodes nativos do ComfyUI), salvo como WEBP animado."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": c["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": c["clip"], "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": c["vae"]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": c["negative"], "clip": ["2", 0]}},
        "6": {"class_type": "EmptyHunyuanLatentVideo",
              "inputs": {"width": c["width"], "height": c["height"], "length": c["length"], "batch_size": 1}},
        "7": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": c["shift"]}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["7", 0], "seed": _seed(), "steps": c["steps"], "cfg": c["cfg"],
            "sampler_name": c["sampler"], "scheduler": c["scheduler"],
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveAnimatedWEBP", "inputs": {
            "images": ["9", 0], "filename_prefix": "jarvis_vid", "fps": c["fps"],
            "lossless": False, "quality": 85, "method": "default"}},
    }
