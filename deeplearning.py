from runx.logx import logx
import torch
import torch.nn as nn
from torch.autograd import Variable
import torch.nn.functional as F
import numpy as np
def train_target_model(args, model, train_loader, optimizer, epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.cuda(), target.cuda()
        optimizer.zero_grad()
        output = model(data)
        loss = F.cross_entropy(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % args.log_interval == 0:
            logx.msg('TargetModel Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch,
                batch_idx * len(data),
                len(train_loader.dataset),
                100. * batch_idx / len(train_loader),
                loss.item()))

def test_target_model(args, model, test_loader, epoch, save=True):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.cuda(), target.cuda()
            output = model(data)
            test_loss += F.cross_entropy(output, target).item()
            pred = output.max(1, keepdim=True)[1]
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)

    accuracy = 100. * correct / len(test_loader.dataset)
    logx.msg('\nTargetModel Test: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset), accuracy))

    # save model
    if save:
        save_dict = {
            'epoch': epoch + 1,
            'state_dict': model.state_dict(),
            'accuracy': accuracy}
        logx.save_model(
            save_dict,
            metric=accuracy,
            epoch='',
            higher_better=True)

    return accuracy/100.

def train_shadow_model(args, targetmodel, shadowmodel, train_loader, optimizer, epoch):
    targetmodel.eval()
    shadowmodel.train()
    for batch_idx, (data, _) in enumerate(train_loader):
        data = data.cuda()
        output = targetmodel(data)
        _, target = output.max(1)
        optimizer.zero_grad()
        output = shadowmodel(data)
        loss = F.cross_entropy(output, target)
        loss.backward()
        optimizer.step()
        if batch_idx % args.log_interval == 0:
            logx.msg('ShadowModel Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                epoch,
                batch_idx * len(data),
                len(train_loader.dataset),
                100. * batch_idx / len(train_loader),
                loss.item()))

def test_shadow_model(args, targetmodel, shadowmodel, test_loader, epoch, save=True):
    targetmodel.eval()
    shadowmodel.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for batch_idx, (data, _) in enumerate(test_loader):
            data = data.cuda()
            output = targetmodel(data)
            _, target = output.max(1)

            output = shadowmodel(data)
            test_loss += F.cross_entropy(output, target).item()
            pred = output.max(1, keepdim=True)[1]
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)

    accuracy = 100. * correct / len(test_loader.dataset)
    logx.msg('\nShadowModel Test: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        test_loss, correct, len(test_loader.dataset), accuracy))
    # save model
    if save:
        save_dict = {
            'epoch': epoch + 1,
            'state_dict': shadowmodel.state_dict(),
            'accuracy': accuracy}
        logx.save_model(
            save_dict,
            metric=accuracy,
            epoch='',
            higher_better=True)
    return accuracy/100.

def train_salem_attack_model(args, shadowmodel, attackmodel, train_loader, test_loader, optimizer, epoch, save=True):
    shadowmodel.eval()
    attackmodel.train()
    test_loss = 0
    correct = 0
    data_loader = zip(train_loader, test_loader)
    for batch_idx, (traindata, testdata)in enumerate(data_loader):
        mem_data, member_target = traindata
        non_data, non_target = testdata

        mem_data, member_target = mem_data.cuda(), member_target.cuda()
        non_data, non_target = non_data.cuda(), non_target.cuda()

        member_target = member_target * 0 + 1
        non_target = non_target * 0 + 0

        data = torch.cat([mem_data, non_data], dim=0)
        target = torch.cat([member_target, non_target], dim=0)

        output = shadowmodel(data)
        output = F.softmax(output, dim=1)
        attackdata = torch.topk(output, 3)[0]
       

        optimizer.zero_grad()
        output = attackmodel(attackdata.detach())
        loss = F.cross_entropy(output, target)         
        loss.backward()         
        optimizer.step()  

        pred = output.max(1, keepdim=True)[1]             
        correct += pred.eq(target.view_as(pred)).sum().item()   

        if batch_idx % args.log_interval == 0:             
            logx.msg('Salem Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(                 
            epoch,                 
            batch_idx * len(data),                 
            len(train_loader.dataset)*2,                 
            100. * batch_idx / (len(train_loader)*2),                 
            loss.item()))
    test_loss /= (len(train_loader.dataset) *2)

    accuracy = 100. * correct / (len(train_loader.dataset)*2)

    # save model
    if save:
        save_dict = {
            'epoch': epoch + 1,
            'arch': '',
            'state_dict': attackmodel.state_dict(),
            'accuracy': accuracy}

        logx.save_model(
            save_dict,
            metric=accuracy,
            epoch='',
            higher_better=True)

def test_salem_attack_model(shadowmodel, attackmodel, data_loader, type=0):     
    shadowmodel.eval()     
    attackmodel.eval()
    test_loss = 0     
    correct = 0          
    with torch.no_grad():         
        for data, target in data_loader:             
            data, target = data.cuda(), target.cuda()
            output = shadowmodel(data)   
            output = F.softmax(output, dim=1)      
            attackdata = torch.topk(output, 3)[0]         
            target = target * 0 + type

            output = attackmodel(attackdata)             
            test_loss += F.cross_entropy(output, target).item()             
            pred = output.max(1, keepdim=True)[1]             
            correct += pred.eq(target.view_as(pred)).sum().item()      
    test_loss /= len(data_loader.dataset)      
    accuracy = 100. * correct / len(data_loader.dataset)     
    logx.msg('\nSalme Test: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(test_loss, correct, len(data_loader.dataset), accuracy))


