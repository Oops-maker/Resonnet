# Image & Video Generation Skill

Generate images and videos using Alibaba DashScope models.

## When to Use

- Create visual content for explanations
- Generate diagrams or illustrations
- Produce video content from descriptions
- Edit existing images

## Recommended: Text to Image with Qwen-Image 2.0 Pro

Use the DashScope **multimodal-generation** endpoint with `qwen-image-2.0-pro`.

```bash
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer ${DASHSCOPE_API_KEY}" \
  --data '{
    "model": "qwen-image-2.0-pro",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": [
            {
              "text": "一副典雅庄重的对联悬挂于厅堂之中，房间是个安静古典的中式布置，桌子上放着一些青花瓷，对联上左书“义本生知人机同道善思新”，右书“通云赋智乾坤启数高志远”，横批“智启千问”，字体飘逸，在中间挂着一幅中国风的画作，内容是岳阳楼。"
            }
          ]
        }
      ]
    },
    "parameters": {
      "size": "1024*1024",
      "negative_prompt": "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感，构图混乱，文字模糊，扭曲。",
      "prompt_extend": true,
      "watermark": false
    }
  }'
```

### Important Parameters

- `size`: Image resolution, e.g. `"1024*1024"`, `"768*1344"`.
- `negative_prompt`: Things you **do not** want in the image.
- `prompt_extend`: `true` to let the model automatically expand your prompt.
- `watermark`: `false` to disable visible watermarks if the service allows.

### Simpler English Example

```bash
curl --location 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer ${DASHSCOPE_API_KEY}" \
  --data '{
    "model": "qwen-image-2.0-pro",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": [
            {
              "text": "A photorealistic portrait of a scientist working in a modern AI lab, soft lighting, 4K resolution."
            }
          ]
        }
      ]
    },
    "parameters": {
      "size": "1024*1024"
    }
  }'
```

## Best Practices

- **Detailed prompts**: Include style, lighting, composition, colors.
- **Language**: Chinese prompts are fully supported; English is also OK.
- **Iterate**: Generate multiple variants and refine.
- **Specify format**: Indicate photo vs illustration style when relevant.

## Example Prompts

- "A modern laboratory with scientists working, photorealistic, bright lighting"
- "Diagram showing DNA structure, scientific illustration style, clean lines"
- "日落时分的岳阳楼远景，中国传统水墨风格，淡雅配色"
