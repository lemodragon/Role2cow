# Role2cow 插件

## 概述

这是 chatgpt-on-wechat 官方 Role 插件的定制版本。此修改的主要目的是使个性化的私人角色能够使用自建知识库，同时系统提示词角色继续使用官方 ChatGPT API。这种分离允许更加可控和个性化的模型请求。

## 特性

1. **个性化角色请求**：自定义角色现在可以使用自建知识库。
2. **API 调用分流**：系统提示词角色仍然使用官方 ChatGPT API。
3. **增强控制**：更好地控制模型请求和知识库访问。
4. **灵活性**：用户可以根据需求选择个性化角色或系统角色。

## 安装

1. 克隆仓库或下载插件文件。
2. 将插件文件放置在 chatgpt-on-wechat 安装目录的 `plugins/role` 文件夹中。
3. 确保已安装所需的依赖项。

## 配置

### 1. config.json

此文件包含云助手 API 的配置。请用您的 API 详细信息修改它：

```json
{
  "cloud_assistant": {
    "api_url": "https://example.com/v1/chat/completions",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "model": "yun-2.0"
  }
}
```

### 2. roles.json

此文件定义了可用的角色。"数字人-云"角色被设置为使用云助手：

```json
{
  "roles": [
    {
      "title": "数字人-云",
      "description": "[I am your digital human assistant cloud, an intelligent assistant developed based on advanced AI technology...]",
      "descn": "[我是你的数字人助手云，一个基于先进AI技术开发的智能助手...]",
      "wrapper": "%s",
      "remark": "私人化定制'数字人-云'角色",
      "tags": [
        "favorite",
        "text"
      ]
    },
    // ... 其他角色 ...
  ]
}
```

## 使用方法

1. **列出可用角色**：
   ```
   $角色列表
   ```

2. **设置角色**：
   ```
   $角色 [角色名称]
   ```
   例如：`$角色 数字人-云`

3. **自定义角色设置**：
   ```
   $设定扮演 [角色描述]
   ```

4. **停止角色扮演**：
   ```
   $停止扮演
   ```

## 工作原理

- 当用户设置一个角色时，插件会检查是否是"数字人-云"角色。**(如果修改请替换包括role.py和roles.json中该对应的关键词)**
- 如果是，它会使用 CloudAssistant 类来调用您的自定义知识库 API。
- 对于其他角色，它使用默认的 ChatGPT 处理。

## 自定义

要添加更多使用自定义 API 的个性化角色：
1. 在 `roles.json` 中添加新的角色条目。
2. 在 `role.py` 的 `Role` 类中，添加逻辑来识别您的新自定义角色，并使用 CloudAssistant 进行处理。

## 故障排除

- 确保您的 API 密钥和 URL 在 `config.json` 中正确设置。
- 检查日志中是否有与 API 调用或角色设置相关的错误消息。

## 贡献

欢迎 fork 此仓库并提交 pull request 以增强功能或修复 bug。
